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

from zope.component.hooks import setHooks
from zope.component.hooks import site as current_site

from zope.intid.interfaces import IIntIds

from nti.app.products.gradebook.gradebook import gradebook_for_course

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeBookPart
from nti.app.products.gradebook.interfaces import IGradeBookEntry

from nti.contentlibrary.interfaces import IContentPackageLibrary

from nti.contenttypes.courses.interfaces import ICourseCatalog
from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser
from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import IX_MIMETYPE
from nti.dataserver.metadata.index import get_metadata_catalog

from nti.dataserver.users.users import User

from nti.intid.common import removeIntId

from nti.site.hostpolicy import get_all_host_sites

from nti.traversal.traversal import find_interface

generation = 10

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


def check_tree(btree):
    # pylint: disable=protected-access
    keys_len = len(btree.keys())
    b_len = btree._BTreeContainer__len
    if keys_len != b_len.value:
        b_len.set(keys_len)
        btree._p_changed = True


def process_course(course):
    book = gradebook_for_course(course, False)
    if book is None:
        return
    # check trees. if alpha we have seen KeyError
    # want to make sure the tree Length object value
    # is the same as its keys
    check_tree(book)
    for part in book.values():
        check_tree(part)
        for entry in part.values():
            check_tree(entry)
    # remove invalid users
    for username in tuple(book.iter_usernames()):
        user = User.get_user(username)
        if not IUser.providedBy(user):
            book.remove_user(username)


def process_catalog(catalog, intids, seen):
    if catalog is None or catalog.isEmpty():
        return
    for entry in catalog.iterCatalogEntries():
        course = ICourseInstance(entry)
        doc_id = intids.queryId(course)
        if doc_id is None or doc_id in seen:
            continue
        seen.add(doc_id)
        process_course(course)


def clear_container(container):
    if container is not None:
        try:
            container.clear()
        except AttributeError:
            pass


def check_grades(intids):
    """
    Check all grades to make sure the are found in a valid course
    """
    metadata = get_metadata_catalog()
    query = {
        IX_MIMETYPE: {'any_of': ('application/vnd.nextthought.grade',)}
    }
    for doc_id in metadata.apply(query) or ():
        grade = intids.queryObject(doc_id)
        if not IGrade.providedBy(grade):
            continue
        course = find_interface(grade, ICourseInstance, strict=False)
        doc_id = intids.queryId(course)
        if doc_id is None:  # invalid course
            logger.warning("Removing invalid grade %s", grade)
            # if we cannot find a course then try to clear as much
            # as possible in the lineage
            book = find_interface(grade, IGradeBook, strict=False)
            part = find_interface(grade, IGradeBookPart, strict=False)
            entry = find_interface(grade, IGradeBookEntry, strict=False)
            clear_container(entry)
            clear_container(part)
            clear_container(book)
            # check removal
            if intids.queryId(grade) is not None:
                removeIntId(grade)
                

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

    seen = set()
    with current_site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        # load library
        library = component.queryUtility(IContentPackageLibrary)
        if library is not None:
            library.syncContentPackages()

        # global site
        catalog = component.queryUtility(ICourseCatalog)
        process_catalog(catalog, intids, seen)

        # all sites
        for host_site in get_all_host_sites():
            with current_site(host_site):
                catalog = component.queryUtility(ICourseCatalog)
                process_catalog(catalog, intids, seen)

        # check invalid grades
        check_grades(intids)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Gradebook evolution %s done', generation)


def evolve(context):
    """
    Evolve to generation 10 by checking the gradebook trees and remove 
    invalid entries
    """
    do_evolve(context, generation)
