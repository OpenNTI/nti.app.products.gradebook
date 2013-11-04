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

from nti.dataserver import users

from . import _adapters as adapters
from . import interfaces as grade_interfaces

@component.adapter(grade_interfaces.IGradeRemovedEvent)
def _grade_removed(event):
	username = event.username
	user = users.User.get_user(username)
	grade = grade_interfaces.IGrade(event.object)
	if user is not None:
		note = adapters.get_grade_discussion_note(user, grade)
		if note is not None:
			user.deleteEqualContainedObject(note)

@component.adapter(grade_interfaces.IGradeBookEntry, lce_interfaces.IObjectRemovedEvent)
def _gradebook_entry_removed(gbe, event):
	grades = None # TODO: Get grades
	if grades:
		grades.remove_grades(gbe.NTIID)
