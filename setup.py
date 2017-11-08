import codecs
import platform
from setuptools import setup
from setuptools import find_packages

py_impl = getattr(platform, 'python_implementation', lambda: None)
IS_PYPY = py_impl() == 'PyPy'

entry_points = {
    'console_scripts': [
        "nti_grade_calculator = nti.app.products.gradebook.grading.scripts.nti_grade_calculator:main",
        "nti_grade_assignment_submissions = nti.app.products.gradebook.scripts.nti_grade_assignment_submissions:main"
    ],
    "z3c.autoinclude.plugin": [
        'target = nti.app.products',
    ],
}


TESTS_REQUIRE = [
    'nti.app.testing',
    'nti.testing',
    'zope.dottedname',
    'zope.testrunner',
]


def _read(fname):
    with codecs.open(fname, encoding='utf-8') as f:
        return f.read()


setup(
    name='nti.app.products.gradebook',
    version=_read('version.txt').strip(),
    author='Jason Madden',
    author_email='jason@nextthought.com',
    description="Support for storing gradebooks",
    long_description=(_read('README.rst') + '\n\n' + _read('CHANGES.rst')),
    license='Apache',
    keywords='pyramid products gradebook',
    classifiers=[
        'Framework :: Zope',
        'Framework :: Pyramid',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: OS Independent',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: Implementation :: CPython',
        'Programming Language :: Python :: Implementation :: PyPy',
    ],
    url="https://github.com/NextThought/nti.app.products.gradebook",
    zip_safe=True,
    packages=find_packages('src'),
    package_dir={'': 'src'},
    include_package_data=True,
    namespace_packages=['nti', 'nti.app', 'nti.app.products'],
    tests_require=TESTS_REQUIRE,
    install_requires=[
        'setuptools',
        'BTrees',
        # fastnumbers: from natsort 3.4.1: 'natsort' will now use the
        # 'fastnumbers' module if it is installed. This gives up to an
        # extra 30% boost in speed over the previous performance
        # enhancements.
        'fastnumbers' if not IS_PYPY else '',
        'natsort',
        'nti.app.assessment',
        'nti.app.client_preferences',
        'nti.assessment',
        'nti.base',
        'nti.common',
        'nti.containers',
        'nti.contentlibrary',
        'nti.contenttypes.courses',
        'nti.dublincore',
        'nti.externalization',
        'nti.links',
        'nti.mimetype',
        'nti.ntiids',
        'nti.property',
        'nti.site',
        'nti.traversal',
        'nti.schema',
        'nti.wref',
        'nti.zodb',
        'nti.zope_catalog',
        'persistent',
        'pyramid',
        'requests',
        'six',
        'zope.cachedescriptors',
        'zope.component',
        'zope.container',
        'zope.i18nmessageid',
        'zope.interface',
        'zope.intid',
        'zope.lifecycleevent',
        'zope.location',
        'zope.mimetype',
        'zope.schema',
        'zope.security',
        'zope.traversing',
    ],
    extras_require={
        'test': TESTS_REQUIRE,
        'docs': [
            'Sphinx',
            'repoze.sphinx.autointerface',
            'sphinx_rtd_theme',
        ],
    },
    entry_points=entry_points
)
