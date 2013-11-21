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

from pyramid.traversal import find_interface

from nti.app.assessment import interfaces as appa_interfaces

from nti.dataserver import interfaces as nti_interfaces

from . import interfaces as grade_interfaces

@component.adapter(grade_interfaces.IGradeBookEntry, lce_interfaces.IObjectRemovedEvent)
def _gradebook_entry_removed(entry, event):
	gradebook = find_interface(entry, grade_interfaces.IGradeBook)
	if gradebook is None:
		__traceback_info__ = entry
		raise TypeError("Unable to find gradebook")
	grades = grade_interfaces.IGrades(gradebook)
	grades.remove_grades(entry.NTIID)

@component.adapter(appa_interfaces.IUsersCourseAssignmentHistoryItem,
				   lce_interfaces.IObjectAddedEvent)
def _assignment_history_item_added(item, event):
	assignmentId = item.__name__  # by definition
	user = nti_interfaces.IUser(item)  # get user
	print(assignmentId, user)
