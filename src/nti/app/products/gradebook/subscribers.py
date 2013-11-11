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

from . import adapters
from . import interfaces as grade_interfaces

@component.adapter(grade_interfaces.IGradeRemovedEvent)
def _grade_removed(event):
	grade = event.object
	discussion = adapters.get_grade_discussion(grade)
	if discussion is not None:
		user = users.User.get_user(grade.username)
		user.deleteEqualContainedObject(discussion)

@component.adapter(grade_interfaces.IGradeBookEntry, lce_interfaces.IObjectRemovedEvent)
def _gradebook_entry_removed(gbe, event):
	grades = getattr(gbe, '__parent__', None)
	if grades:
		grades.remove_grades(gbe.NTIID)
