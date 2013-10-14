#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import
__docformat__ = "restructuredtext en"

from zope import schema
from zope import interface
from zope.interface.common.mapping import IMapping
from zope.container.constraints import contains, containers
from zope.container.interfaces import IContainer, IContained

from nti.utils import schema as dmschema

class IGradeBookEntry(IContained):

	containers(b'.IGradeBookPart')

	NTIID = dmschema.ValidTextLine(title="entry ntiid", required=True)
	questionSetID = dmschema.ValidTextLine(title="question id", required=False)
	name = dmschema.ValidTextLine(title="entry name", required=True)
	weight = schema.Float(title="The relative weight of this entry, from 0 to 1",
						  min=0.0,
						  max=1.0,
						  default=1.0)

	order = schema.Int(title="The entry order", min=1)

class IGradeBookPart(IContainer, IContained):
	"""
	A Section of a grade book e.g. Quizzes, Exams, etc..
	"""
	containers(b'.IGradeBook')
	contains(IGradeBookEntry)
	__parent__.required = False

	name = dmschema.ValidTextLine(title="Part name", required=True)

	weight = schema.Float(title="The relative weight of this part, from 0 to 1",
						  min=0.0,
						  max=1.0,
						  default=1.0,
						  required=True)

	order = schema.Int(title="The part order", min=1)

class IGradeBook(IContainer, IContained):
	"""
	Grade book definition
	"""
	contains(IGradeBookPart)
	__parent__.required = False


class IGrade(interface.Interface):
	"""
	Grade entry
	"""
	entry = dmschema.ValidTextLine(title="grade entry ntiid", required=True)
	grade = schema.Float(title="The real grade", min=0.0, max=100.0, required=False)
	autograde = schema.Float(title="Auto grade", min=0.0, max=100.0, required=False)

class IGrades(IMapping):
	"""
	User grades
	"""
	
	def get_grades(username):
		pass

	def add_grade(username, grade):
		pass

	def remove_grade(username, grade):
		pass
