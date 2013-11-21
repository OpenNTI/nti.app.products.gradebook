#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
Gradebook event subscribers

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope.lifecycleevent import interfaces as lce_interfaces

from nti.app.assessment import interfaces as appa_interfaces

from . import interfaces as grade_interfaces

@component.adapter(grade_interfaces.IGradeBookEntry, lce_interfaces.IObjectRemovedEvent)
def _gradebook_entry_removed(gbe, event):
	grades = getattr(gbe, '__parent__', None)
	if grades:
		grades.remove_grades(gbe.NTIID)


@component.adapter(appa_interfaces.IUsersCourseAssignmentHistoryItem,
				   lce_interfaces.IObjectAddedEvent)
def _assignment_history_item_added(item, event):

	assignmentId = getattr(item.Submission, 'assignmentId',
						   getattr(item.pendingAssessment, 'assignmentId', None))

	print(assignmentId)
