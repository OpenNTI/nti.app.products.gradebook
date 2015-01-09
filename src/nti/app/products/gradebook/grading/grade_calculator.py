#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from nti.monkey import relstorage_patch_all_except_gevent_on_import
relstorage_patch_all_except_gevent_on_import.patch()

import os
import argparse
import importlib

from zope.component import hooks

from zope.configuration import xmlconfig, config
from zope.dottedname import resolve as dottedname

from zope.container.contained import Contained

import zope.browserpage

from z3c.autoinclude.zcml import includePluginsDirective

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.utils import run_with_dataserver

from nti.ntiids.ntiids import find_object_with_ntiid

from nti.site.site import get_site_for_site_names

from ..interfaces import IGradeScheme

from . import calculate_grades

class PluginPoint(Contained):

	def __init__(self, name):
		self.__name__ = name

PP_APP = PluginPoint('nti.app')
PP_APP_SITES = PluginPoint('nti.app.sites')
PP_APP_PRODUCTS = PluginPoint('nti.app.products')

def create_context(env_dir=None, with_library=True):
	etc = os.getenv('DATASERVER_ETC_DIR') or os.path.join(env_dir, 'etc')
	etc = os.path.expanduser(etc)

	context = config.ConfigurationMachine()
	xmlconfig.registerCommonDirectives(context)

	slugs = os.path.join(etc, 'package-includes')
	if os.path.exists(slugs) and os.path.isdir(slugs):
		package = dottedname.resolve('nti.dataserver')
		context = xmlconfig.file('configure.zcml', package=package, context=context)
		xmlconfig.include(context, files=os.path.join(slugs, '*.zcml'),
						  package='nti.appserver')

	if with_library:
		library_zcml = os.path.join(etc, 'library.zcml')
		if not os.path.exists(library_zcml):
			raise Exception("Could not locate library zcml file %s", library_zcml)
		xmlconfig.include(context, file=library_zcml, package='nti.appserver')
		
	# Include zope.browserpage.meta.zcm for tales:expressiontype
	# before including the products
	xmlconfig.include(context, file="meta.zcml", package=zope.browserpage)

	# include plugins
	includePluginsDirective(context, PP_APP)
	includePluginsDirective(context, PP_APP_SITES)
	includePluginsDirective(context, PP_APP_PRODUCTS)
	
	return context

def _process_args(ntiid, scheme, entry_name='Current_Grade', site=None):
	module_name, class_name = scheme.rsplit(".", 1)
	module = importlib.import_module(module_name)
	clazz = getattr(module, class_name)
	grade_scheme = clazz()
	if IGradeScheme.providedBy(grade_scheme):
		raise ValueError("Invalid grade scheme class")

	if site:
		cur_site = hooks.getSite()
		new_site = get_site_for_site_names( (site,), site=cur_site )
		if new_site is cur_site:
			raise ValueError("Unknown site name", site)
		hooks.setSite(new_site)
	
	context = find_object_with_ntiid(ntiid)
	course = ICourseInstance(context, None)
	if course is None:
		raise ValueError("Unknown course", ntiid)

	result = calculate_grades(course, grade_scheme, entry_name=entry_name)
	return result

def main():
	arg_parser = argparse.ArgumentParser(description="Grade calculator")
	arg_parser.add_argument('-v', '--verbose', help="Be verbose", action='store_true',
							 dest='verbose')
	
	arg_parser.add_argument('course', help="Course NTIID")
	
	arg_parser.add_argument('-s', '--site', dest='site', help="Request site")
	
	arg_parser.add_argument('-g', '--grade', dest='scheme', help="Grade scheme class name",
							default='nti.app.products.gradebook.gradescheme.LetterGradeScheme')
	
	arg_parser.add_argument('-e', '--entry', dest='entry', help="Grade entry name",
							default='Current_Grade')
	
	args = arg_parser.parse_args()
	verbose = args.verbose
	
	site = args.site
	if not site and verbose:
		print('WARN: NO site specified')

	env_dir = os.getenv('DATASERVER_DIR')
	context = create_context(env_dir)
	conf_packages = ('nti.appserver',)
	run_with_dataserver(environment_dir=env_dir,
						verbose=verbose,
						context=context,
						minimal_ds=True,
						xmlconfig_packages=conf_packages,
						function=lambda: _process_args(	site=site,
														entry=args.entry,
														ntiid=args.course,
														scheme=args.scheme))

if __name__ == '__main__':
	main()
	