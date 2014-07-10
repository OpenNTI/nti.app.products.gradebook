from setuptools import setup, find_packages
import codecs

VERSION = '0.0.0'

entry_points = {
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
		'natsort'
	],
	entry_points=entry_points
)
