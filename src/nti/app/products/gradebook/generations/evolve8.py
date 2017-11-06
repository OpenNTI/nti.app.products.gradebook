#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.app.products.gradebook.index import install_grade_catalog

from nti.app.products.gradebook.interfaces import IGrade

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import IX_MIMETYPE
from nti.dataserver.metadata.index import get_metadata_catalog

generation = 8

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid,
                                              ignore_creator=ignore_creator)
        return None


def do_evolve(context, generation=generation):
    logger.info("Gradebook evolution %s started", generation)

    setHooks()
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']
    lsm = ds_folder.getSiteManager()
    intids = lsm.getUtility(IIntIds)

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)

    with site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        catalog = install_grade_catalog(ds_folder, intids)
        metadata = get_metadata_catalog()
        query = {
            IX_MIMETYPE: {'any_of': ('application/vnd.nextthought.grade',)}
        }
        count = 0
        for uid in metadata.apply(query) or ():
            grade = intids.queryObject(uid)
            if IGrade.providedBy(grade):
                count += 1
                catalog.index_doc(uid, grade)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Gradebook evolution %s done, %s grade(s) indexed',
                generation, count)


def evolve(context):
    """
    Evolve to generation 8 by re-indexing the grade catalog
    """
    do_evolve(context, generation)
