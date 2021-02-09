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

from zope.annotation.interfaces import IAnnotations

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.app.products.gradebook.interfaces import IGradeBookEntry
from nti.app.products.gradebook.interfaces import IGradeChangeContainer

from nti.app.products.gradebook.subscribers.grades import _CHANGE_KEY

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import get_metadata_catalog

generation = 11

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warning("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator)
        return None


def do_evolve(context, generation=generation):  # pylint: disable=redefined-outer-name
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

        metadata = get_metadata_catalog()
        query = {
            'mimeType': {'any_of': ('application/vnd.nextthought.gradebookentry',)}
        }
        for uid in metadata.apply(query) or ():
            entry = intids.queryObject(uid)
            if IGradeBookEntry.providedBy(entry):
                annotes = IAnnotations(entry)
                changes = annotes.get(_CHANGE_KEY)
                if changes is not None:
                    interface.alsoProvides(changes, IGradeChangeContainer)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Gradebook evolution %s done', generation)


def evolve(context):
    """
    Evolve to generation 11 by marking change entry containers.
    """
    do_evolve(context, generation)
