#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

generation = 4

import zope.intid

from zope.catalog.interfaces import ICatalog

import BTrees

from nti.dataserver.interfaces import IMetadataCatalog

from ..index import CATALOG_NAME
from ..index import MetadataGradeCatalog
		
def do_evolve(context, generation=generation):
	logger.info("Gradebook evolution %s started", generation);
	
	conn = context.connection
	ds_folder = conn.root()['nti.dataserver']
	lsm = ds_folder.getSiteManager()
	intids = lsm.getUtility(zope.intid.IIntIds)
	
	## unregister old catalog
	old_catalog = lsm.getUtility(ICatalog, name=CATALOG_NAME)
	intids.unregister(old_catalog)
	lsm.unregisterUtility( old_catalog, provided=ICatalog, name=CATALOG_NAME )
	old_catalog.__parent__ = None

	## Add our new catalog
	new_catalog = MetadataGradeCatalog( family=BTrees.family64 )
	new_catalog.__parent__ = ds_folder
	new_catalog.__name__ = CATALOG_NAME
	intids.register(new_catalog)
	lsm.registerUtility(new_catalog, provided=IMetadataCatalog, name=CATALOG_NAME)

	## Migrate indexes
	for k, v in old_catalog.items():
		# Avoid firing re-index event...
		new_catalog._setitemf( k, v )
			
	logger.info('Gradebook evolution %s done' ,generation)
		
def evolve(context):
	"""
	Evolve to generation 4 by re-registering the grade catalog index
	"""
	do_evolve(context, generation)
