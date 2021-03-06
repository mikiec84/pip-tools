import pytest

from piptools.exceptions import UnsupportedConstraint


@pytest.mark.parametrize(
    ("input", "expected", "prereleases"),
    (
        (tup + (False,))[:3]
        for tup in [
            (["Django"], ["django==1.8"]),
            (
                ["Flask"],
                [
                    "flask==0.10.1",
                    "itsdangerous==0.24",
                    "markupsafe==0.23",
                    "jinja2==2.7.3",
                    "werkzeug==0.10.4",
                ],
            ),
            (["Jinja2", "markupsafe"], ["jinja2==2.7.3", "markupsafe==0.23"]),
            # We should return a normal release version if prereleases is False
            (["SQLAlchemy"], ["sqlalchemy==0.9.9"]),
            # We should return the prerelease version if prereleases is True
            (["SQLAlchemy"], ["sqlalchemy==1.0.0b5"], True),
            # Ipython has extras available, but we don't require them in this test
            (["ipython"], ["ipython==2.1.0", "gnureadline==6.3.3"]),
            # We should get dependencies for extras
            (
                ["ipython[notebook]"],
                [
                    "ipython[notebook]==2.1.0",
                    "pyzmq==2.1.12",
                    "jinja2==2.7.3",
                    "tornado==3.2.2",
                    "markupsafe==0.23",
                    "gnureadline==6.3.3",
                ],
            ),
            # We should get dependencies for multiple extras
            (
                ["ipython[notebook,nbconvert]"],
                [
                    # Note that the extras should be sorted
                    "ipython[nbconvert,notebook]==2.1.0",
                    "pyzmq==2.1.12",
                    "jinja2==2.7.3",
                    "tornado==3.2.2",
                    "markupsafe==0.23",
                    "gnureadline==6.3.3",
                    "pygments==1.5",
                    "sphinx==0.3",
                ],
            ),
            # We must take the union of all extras
            (
                ["ipython[notebook]", "ipython[nbconvert]"],
                [
                    # Note that the extras should be sorted
                    "ipython[nbconvert,notebook]==2.1.0",
                    "pyzmq==2.1.12",
                    "jinja2==2.7.3",
                    "tornado==3.2.2",
                    "markupsafe==0.23",
                    "gnureadline==6.3.3",
                    "pygments==1.5",
                    "sphinx==0.3",
                ],
            ),
            # We must remove child dependencies from result if parent
            # is removed (e.g. vine from amqp>=2.0)
            # See: GH-370
            # because of upated dependencies in the test index, we need to pin celery
            # in order to reproduce vine removal (because it was readded in later
            # releases)
            (
                ["celery<=3.1.23", "librabbitmq"],
                [
                    "amqp==1.4.9",
                    "anyjson==0.3.3",
                    "billiard==3.5.0.2",
                    "celery==3.1.23",
                    "kombu==3.0.35",
                    "librabbitmq==1.6.1",
                    "pytz==2016.4",
                ],
            ),
            # Support specifying loose top-level requirements that could also appear as
            # pinned subdependencies.
            (
                ["billiard", "celery", "fake-piptools-test-with-pinned-deps"],
                [
                    "amqp==1.4.9",
                    "anyjson==0.3.3",
                    "billiard==3.3.0.23",
                    "celery==3.1.18",  # this is pinned from test subdependency
                    "fake-piptools-test-with-pinned-deps==0.1",
                    "kombu==3.0.35",
                    "pytz==2016.4",
                ],
            ),
            # Exclude package dependcy of setuptools as it is unsafe.
            (["html5lib"], ["html5lib==0.999999999"]),
            # We shouldn't include irrelevant pip constraints
            # See: GH-471
            (
                ["Flask", ("click", True), ("itsdangerous", True)],
                [
                    "flask==0.10.1",
                    "itsdangerous==0.24",
                    "markupsafe==0.23",
                    "jinja2==2.7.3",
                    "werkzeug==0.10.4",
                ],
            ),
            # Unsafe dependencies should be filtered
            (["setuptools==35.0.0", "anyjson==0.3.3"], ["anyjson==0.3.3"]),
            (
                ["fake-piptools-test-with-unsafe-deps==0.1"],
                ["fake-piptools-test-with-unsafe-deps==0.1"],
            ),
        ]
    ),
)
def test_resolver(resolver, from_line, input, expected, prereleases):
    input = [line if isinstance(line, tuple) else (line, False) for line in input]
    input = [from_line(req[0], constraint=req[1]) for req in input]
    output = resolver(input, prereleases=prereleases).resolve()
    output = {str(line) for line in output}
    assert output == {str(line) for line in expected}


@pytest.mark.parametrize(
    ("input", "expected", "prereleases"),
    (
        (tup + (False,))[:3]
        for tup in [
            (
                ["setuptools==34.0.0"],
                ["appdirs==1.4.9", "setuptools==34.0.0", "packaging==16.8"],
            ),
            (
                ["fake-piptools-test-with-unsafe-deps==0.1"],
                [
                    "appdirs==1.4.9",
                    "setuptools==34.0.0",
                    "packaging==16.8",
                    "fake-piptools-test-with-unsafe-deps==0.1",
                ],
            ),
        ]
    ),
)
def test_resolver__allows_unsafe_deps(
    resolver, from_line, input, expected, prereleases
):
    input = [line if isinstance(line, tuple) else (line, False) for line in input]
    input = [from_line(req[0], constraint=req[1]) for req in input]
    output = resolver(input, prereleases=prereleases, allow_unsafe=True).resolve()
    output = {str(line) for line in output}
    assert output == {str(line) for line in expected}


def test_resolver__max_number_rounds_reached(resolver, from_line):
    """
    Resolver should raise an exception if max round has been reached.
    """
    input = [from_line("django")]
    with pytest.raises(RuntimeError, match="after 0 rounds of resolving"):
        resolver(input).resolve(max_rounds=0)


def test_resolver__check_constraints(resolver, from_line):
    """
    Resolver should not support non-editable URLs as packages.
    """
    input = [from_line("django"), from_line("https://example.com/#egg=example")]
    with pytest.raises(
        UnsupportedConstraint, match="pip-compile does not support URLs as packages"
    ):
        resolver(input).resolve()


def test_iter_dependencies(resolver, from_line):
    """
    Dependencies should be pinned or editable.
    """
    ireq = from_line("django>=1.8")
    res = resolver([])

    with pytest.raises(
        TypeError, match="Expected pinned or editable requirement, got django>=1.8"
    ):
        next(res._iter_dependencies(ireq))
