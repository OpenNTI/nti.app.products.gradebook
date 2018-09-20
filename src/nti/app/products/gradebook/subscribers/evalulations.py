#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from pyramid import httpexceptions as hexc

from pyramid.threadlocal import get_current_request

from zope import component

from nti.app.externalization.error import raise_json_error

from nti.app.products.gradebook import MessageFactory as _

from nti.app.products.gradebook.assignments import create_assignment_entry

from nti.app.products.gradebook.interfaces import IGradeBook

from nti.assessment.interfaces import IQAssignment
from nti.assessment.interfaces import IQEditableEvaluation

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.publishing.interfaces import IObjectPublishedEvent
from nti.publishing.interfaces import IObjectUnpublishedEvent

logger = __import__('logging').getLogger(__name__)


@component.adapter(IQEditableEvaluation, IObjectPublishedEvent)
def _on_evalulation_published(item, unused_event=None):
    if IQAssignment.providedBy(item):
        course = ICourseInstance(item, None)
        book = IGradeBook(course, None)
        if book is not None:
            displayName = item.title or _(u'Assignment')
            create_assignment_entry(course, item, displayName, _book=book)


@component.adapter(IQEditableEvaluation, IObjectUnpublishedEvent)
def _on_evalulation_unpublished(item, unused_event=None):
    if IQAssignment.providedBy(item):
        course = ICourseInstance(item, None)
        book = IGradeBook(course, None)
        if book is not None:
            # pylint: disable=too-many-function-args 
            entry = book.getColumnForAssignmentId(item.ntiid)
            if entry:
                request = get_current_request()
                raise_json_error(request,
                                 hexc.HTTPUnprocessableEntity,
                                 {
                                     'message': _(u"Cannot unpublish assignment with grades."),
                                     'code': 'CannotUnpublishObject',
                                 },
                                 None)
