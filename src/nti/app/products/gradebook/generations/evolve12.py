#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 27.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

generation = 12

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.intid.interfaces import IIntIds

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistoryItem

from nti.assessment.interfaces import IPlaceholderAssignmentSubmission

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import get_metadata_catalog

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def _remove_placeholder_submissions(intids):
    removed_count = 0
    metadata_catalog = get_metadata_catalog()
    index = metadata_catalog['mimeType']

    MIME_TYPES = ('application/vnd.nextthought.assessment.userscourseassignmenthistoryitem',)
    item_intids = index.apply({'any_of': MIME_TYPES})
    for doc_id in item_intids or ():
        item = intids.queryObject(doc_id)
        if      IUsersCourseAssignmentHistoryItem.providedBy(item) \
            and IPlaceholderAssignmentSubmission.providedBy(item.Submission):
            removed_count += 1
            user = IUser(item, None)
            if item.Assignment is None:
                # XXX: This is likely a history item without a creator (due to the
                # deleted user. Now this object is in a weird, invalid state (see
                # assessment evolve45.py).
                # Ideally, I think we'd want to remove all of these objects for
                # deleted users.
                logger.info('History item without a user (%s) (%s)', item.ntiid, item.__parent__.__name__)
                continue
            logger.info('Deleting placeholder submission (%s) (%s) (%s)',
                        item.ntiid,
                        getattr(user, 'username', user),
                        item.assignmentId)
            del item.__parent__[item.__name__]
    return removed_count


def do_evolve(context, generation=generation):
    logger.info("Grade container evolution %s started", generation)

    setHooks()
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']
    lsm = ds_folder.getSiteManager()

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)
    intids = lsm.getUtility(IIntIds)

    with site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"
        placeholder_submissions_removed = _remove_placeholder_submissions(intids)
    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Gradebook evolution %s done (placeholder_submissions_removed=%s)',
                generation, placeholder_submissions_removed)


def evolve(context):
    """
    Evolve to generation 12 by removing placeholder submissions.
    """
    do_evolve(context)
