#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook adapters

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

import six

from zope import interface
from zope import component

from ZODB.interfaces import IConnection

from nti.dataserver import users
from nti.dataserver.contenttypes import Note
from nti.dataserver import interfaces as nti_interfaces

from . import grades
from . import interfaces as grade_interfaces

@interface.implementer(grade_interfaces.IGrade)
@component.adapter(basestring)
def _StringGradeAdapter(ntiid):
	return grades.Grade(ntiid=ntiid)

@interface.implementer(grade_interfaces.IGrade)
@component.adapter(grade_interfaces.IGradeBookEntry)
def _EntryGradeAdapter(entry):
	return grades.Grade(ntiid=entry.NTIID)

def get_grade_discussion_note(user, grade):
	result = None
	grade = grade_interfaces.IGrade(grade)
	container = user.getContainer(grade.ntiid, {})
	for obj in container.values():
		# match the first note in container
		if grade_interfaces.IGradeDiscussionNote.providedBy(obj):
			result = obj
	return result

def create_grade_discussion_note(user, grade):
	result = Note()
	result.creator = user
	result.containerId = grade.ntiid
	jar = IConnection(user, None)
	if jar:
		jar.add(result)
	interface.alsoProvides(result, grade_interfaces.IGradeDiscussionNote)
	user.addContainedObject(result)
	return result

@interface.implementer(nti_interfaces.INote)
@component.adapter(nti_interfaces.IUser, grade_interfaces.IGrade)
def _DiscussionGradeAdapter(user, grade):
	if isinstance(user, six.string_types):
		user = users.User.get_entity(user)
	grade = grade_interfaces.IGrade(grade)
	result = get_grade_discussion_note(user, grade)
	result = result if result is not None else create_grade_discussion_note(user, grade)
	return result
