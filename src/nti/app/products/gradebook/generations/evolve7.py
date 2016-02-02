#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 7

from zope import component

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from zope.location import locate

from nti.app.products.gradebook.index import IX_SITE
from nti.app.products.gradebook.index import SiteIndex
from nti.app.products.gradebook.index import install_grade_catalog

from nti.app.products.gradebook.interfaces import IGrade

from nti.dataserver.interfaces import IMetadataCatalog

from nti.dataserver.metadata_index import CATALOG_NAME

def do_evolve(context, generation=generation):
	logger.info("Gradebook evolution %s started", generation);

	setHooks()
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']
	lsm = ds_folder.getSiteManager()
	intids = lsm.getUtility(IIntIds)

	with site(ds_folder):
		assert 	component.getSiteManager() == ds_folder.getSiteManager(), \
				"Hooks not installed?"

		catalog = install_grade_catalog(ds_folder, intids)
		if IX_SITE not in catalog:
			index = SiteIndex(family=intids.family)
			intids.register(index)
			locate(index, catalog, IX_SITE)
			catalog[IX_SITE] = index
	
			metadata = lsm.getUtility(IMetadataCatalog, name=CATALOG_NAME)
			query = {
				'mimeType': {'any_of': ('application/vnd.nextthought.grade',)}
			}
			for uid in metadata.apply(query) or ():
				grade = intids.queryObject(uid)
				if IGrade.providedBy(grade):
					index.index_doc(uid, grade)

	logger.info('Gradebook evolution %s done' , generation)

def evolve(context):
	"""
	Evolve to generation 7 by re-registering the grade catalog index
	"""
	do_evolve(context, generation)
