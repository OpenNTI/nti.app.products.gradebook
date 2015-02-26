import codecs
import platform
from setuptools import setup, find_packages

VERSION = '0.0.0'

py_impl = getattr(platform, 'python_implementation', lambda: None)
IS_PYPY = py_impl() == 'PyPy'

entry_points = {
    'console_scripts': [
        "nti_grade_calculator = nti.app.products.gradebook.grading.scripts.grade_calculator:main"
    ],
    "z3c.autoinclude.plugin": [
		'target = nti.app.products',
	],
}

setup(
	name='nti.app.products.gradebook',
	version=VERSION,
	author='Jason Madden',
	author_email='jason@nextthought.com',
	description="Support for storing gradebooks",
	long_description=codecs.open('README.rst', encoding='utf-8').read(),
	license='Proprietary',
	keywords='pyramid preference',
	classifiers=[
		'Intended Audience :: Developers',
		'Natural Language :: English',
		'Operating System :: OS Independent',
		'Programming Language :: Python :: 2',
		'Programming Language :: Python :: 2.7',
		'Programming Language :: Python :: 3',
		'Programming Language :: Python :: 3.3',
		'Topic :: Software Development :: Testing'
		'Framework :: Pyramid',
		],
	packages=find_packages('src'),
	package_dir={'': 'src'},
	namespace_packages=['nti', 'nti.app', 'nti.app.products'],
	install_requires=[
		'setuptools',
		'nti.app.assessment',
		'nti.contenttypes.courses',
		'nti.dataserver',
		'natsort',
		# fastnumbers: from natsort 3.4.1: 'natsort' will now use the
		# 'fastnumbers' module if it is installed. This gives up to an
		# extra 30% boost in speed over the previous performance
		# enhancements.
		'fastnumbers' if not IS_PYPY else '',
	],
	entry_points=entry_points
)
