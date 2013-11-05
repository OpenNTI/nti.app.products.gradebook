#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook adapters

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from ZODB.interfaces import IConnection

from nti.dataserver import users
from nti.dataserver.contenttypes import Note
from nti.dataserver import interfaces as nti_interfaces

from . import interfaces as grade_interfaces

def get_grade_discussion_note(grade, username=None):
	result = None
	username = username or grade.username
	user = users.User.get_user(username)
	ntiid = getattr(grade, 'ntiid', unicode(grade))
	container = user.getContainer(ntiid, {}) if user is not None else {}
	for obj in container.values():
		if grade_interfaces.IGradeDiscussionNote.providedBy(obj):
			result = obj
	return result

def create_grade_discussion_note(grade, username=None):
	username = username or grade.username
	user = users.User.get_user(username)
	if user is None:
		return None
	ntiid = getattr(grade, 'ntiid', unicode(grade))
	# create note
	result = Note()
	result.creator = user
	result.containerId = ntiid
	jar = IConnection(user, None)
	if jar:
		jar.add(result)
	interface.alsoProvides(result, grade_interfaces.IGradeDiscussionNote)
	user.addContainedObject(result)
	return result

@interface.implementer(nti_interfaces.INote)
@component.adapter(grade_interfaces.IGrade)
def _DiscussionGradeAdapter(grade):
	result = get_grade_discussion_note(grade)
	result = result if result is not None else create_grade_discussion_note(grade)
	return result
