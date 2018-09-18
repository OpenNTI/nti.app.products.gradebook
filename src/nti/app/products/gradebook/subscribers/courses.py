#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component

from zope.component.hooks import getSite

from zope.intid.interfaces import IIntIdRemovedEvent

from nti.app.products.gradebook.index import IX_SITE
from nti.app.products.gradebook.index import IX_COURSE
from nti.app.products.gradebook.index import get_grade_catalog

from nti.app.products.gradebook.utils.gradebook import synchronize_gradebook_and_verify_policy

from nti.contenttypes.courses.interfaces import ICourseInstance
from nti.contenttypes.courses.interfaces import ICourseCatalogEntry
from nti.contenttypes.courses.interfaces import ICourseInstanceImportedEvent
from nti.contenttypes.courses.interfaces import ICourseInstanceAvailableEvent

logger = __import__('logging').getLogger(__name__)


@component.adapter(ICourseInstance, ICourseInstanceAvailableEvent)
def _synchronize_gradebook_with_course_instance(course, unused_event=True):
    synchronize_gradebook_and_verify_policy(course)


@component.adapter(ICourseInstance, ICourseInstanceImportedEvent)
def _on_course_instance_imported(course, unused_event=True):
    synchronize_gradebook_and_verify_policy(course)


def unindex_course_data(course):
    entry = ICourseCatalogEntry(course, None)
    if entry is not None:
        catalog = get_grade_catalog()
        query = {
            IX_COURSE: {'any_of': (entry.ntiid,)},
            IX_SITE: {'any_of': (getSite().__name__,)}
        }
        for uid in catalog.apply(query) or ():
            catalog.unindex_doc(uid)


@component.adapter(ICourseInstance, IIntIdRemovedEvent)
def _on_course_instance_removed(course, unused_event=True):
    unindex_course_data(course)
