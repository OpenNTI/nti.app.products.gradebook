#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

from zope import schema
from zope import interface
from zope import lifecycleevent
from zope.interface.common import mapping
from zope.container.constraints import contains, containers
from zope.container.interfaces import IContainer, IContained
from zope.lifecycleevent import interfaces as lce_interfaces

from nti.utils import schema as dmschema

# ## NTIID values

NTIID_TYPE_GRADE_BOOK = 'gradebook'

NTIID_TYPE_GRADE_BOOK_PART = 'gradebookpart'

NTIID_TYPE_GRADE_BOOK_ENTRY = 'gradebookentry'

class ICloneable(interface.Interface):

	def clone():
		"""
		clone this object
		"""
class IGradeDiscussionNote(interface.Interface):
	"""
	marker interface for a discussion/feedback grade note
	"""

class IGradeBookEntry(IContained, ICloneable):

	containers(b'.IGradeBookPart')
	__parent__.required = False

	questionSetID = dmschema.ValidTextLine(title="question id", required=False)
	name = dmschema.ValidTextLine(title="entry name", required=True)
	weight = schema.Float(title="The relative weight of this entry, from 0 to 1",
						  min=0.0,
						  max=1.0,
						  default=1.0)
	order = schema.Int(title="The entry order", min=1)
	
class IGradeBookPart(IContainer, IContained, ICloneable, mapping.IClonableMapping):
	"""
	A Section of a grade book e.g. Quizzes, Exams, etc..
	"""
	containers(b'.IGradeBook')
	contains(b'.IGradeBookEntry')
	__parent__.required = False

	name = dmschema.ValidTextLine(title="Part name", required=True)
	weight = schema.Float(title="The relative weight of this part, from 0 to 1",
						  min=0.0,
						  max=1.0,
						  default=1.0,
						  required=True)
	order = schema.Int(title="The part order", min=1)

	TotalEntryWeight = schema.Float(title="Entry weight sum", readonly=True)

class IGradeBook(IContainer, IContained, ICloneable, mapping.IClonableMapping):
	"""
	Grade book definition
	"""
	contains(b'.IGradeBookPart')
	TotalPartWeight = schema.Float(title="Part weight sum", readonly=True)

class IGrade(IContained, ICloneable):
	"""
	Grade entry
	"""
	ntiid = dmschema.ValidTextLine(title="grade entry ntiid", required=True)
	grade = schema.Float(title="The real grade", min=0.0, max=100.0, required=False)
	autograde = schema.Float(title="Auto grade", min=0.0, max=100.0, required=False)

class IGrades(mapping.IMapping, IContained):
	"""
	User grades
	"""
	
	def get_grades(username):
		pass

	def add_grade(username, grade):
		pass

	def remove_grade(username, grade):
		pass

class IGradeAddedEvent(lce_interfaces.IObjectAddedEvent):
	username = interface.Attribute("username")

@interface.implementer(IGradeAddedEvent)
class GradeAddedEvent(lifecycleevent.ObjectAddedEvent):

	def __init__(self, obj, username, *args, **kwargs):
		super(GradeAddedEvent, self).__init__(obj, *args, **kwargs)
		self.username = username

class IGradeModifiedEvent(lce_interfaces.IObjectModifiedEvent):
	username = interface.Attribute("username")

@interface.implementer(IGradeModifiedEvent)
class GradeModifiedEvent(lifecycleevent.ObjectModifiedEvent):

	def __init__(self, obj, username, *args, **kwargs):
		super(GradeModifiedEvent, self).__init__(obj, *args, **kwargs)
		self.username = username

class IGradeRemovedEvent(lce_interfaces.IObjectRemovedEvent):
	username = interface.Attribute("username")

@interface.implementer(IGradeRemovedEvent)
class GradeRemovedEvent(lifecycleevent.ObjectModifiedEvent):

	def __init__(self, obj, username, *args, **kwargs):
		super(GradeRemovedEvent, self).__init__(obj, *args, **kwargs)
		self.username = username
