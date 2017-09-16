#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component

from zope.catalog.interfaces import ICatalog

from zope.intid.interfaces import IIntIds

from nti.app.products.gradebook.index import IX_STUDENT
from nti.app.products.gradebook.index import CATALOG_NAME

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.contenttypes.courses import get_enrollment_catalog

from nti.contenttypes.courses.index import IX_USERNAME

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IUser

from nti.dataserver.users.interfaces import IWillDeleteEntityEvent


def unindex_grade_data(username):
    result = 0
    catalog = component.queryUtility(ICatalog, name=CATALOG_NAME)
    if catalog is not None:
        index = catalog[IX_STUDENT]
        # normalize
        if isinstance(username, bytes):
            username = username.decode('utf-8')
        username = username.lower().strip()
        # get all doc ids (it's a wrapper)
        values_to_documents = index.index.values_to_documents
        docs = values_to_documents.get(username) or ()
        for uid in tuple(docs):
            catalog.unindex_doc(uid)
            result += 1
    return result


def delete_user_data(user):
    username = user.username
    catalog = get_enrollment_catalog()
    intids = component.getUtility(IIntIds)
    query = {IX_USERNAME: {'any_of': (username,)}}
    for uid in catalog.apply(query) or ():
        context = intids.queryObject(uid)
        course = ICourseInstance(context, None)
        book = IGradeBook(course, None)
        if book is not None:
            book.remove_user(username)


@component.adapter(IUser, IWillDeleteEntityEvent)
def _on_user_will_be_removed(user, unused_event):
    logger.info("Removing gradebook data for user %s", user)
    unindex_grade_data(user.username)
    delete_user_data(user=user)
