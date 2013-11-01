#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grades definition

$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope.event import notify
from zope.location import locate
from zope.container import contained as zcontained
from zope.annotation import interfaces as an_interfaces
from zope.mimetype import interfaces as zmime_interfaces

from zc.blist import BList

from persistent.mapping import PersistentMapping

from nti.dataserver import mimetype
from nti.dataserver.datastructures import ModDateTrackingObject

from nti.externalization import internalization
from nti.externalization import interfaces as ext_interfaces

from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

from . import interfaces as grades_interfaces

@interface.implementer(grades_interfaces.IGrade,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class Grade(ModDateTrackingObject, SchemaConfigured, zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	createDirectFieldProperties(grades_interfaces.IGrade)

	def __eq__(self, other):
		try:
			return self is other or (self.ntiid == other.ntiid)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.ntiid)
		return xhash

	def __str__(self):
		return "%s,%s" % (self.ntiid, self.grade)

	def __repr__(self):
		return "%s(%s,%s,%s)" % (self.__class__.__name__,
								 self.ntiid,
								 self.grade,
								 self.autograde)

@interface.implementer(grades_interfaces.IGrades, 
					   ext_interfaces.IInternalObjectUpdater,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class Grades(PersistentMapping, zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	def index(self, username, grade, grades=()):
		ntiid = grades_interfaces.IGrade(grade).ntiid

		idx = -1
		grades = grades or self.get(username, ())
		grade = unicode(grade)
		for i, g in enumerate(grades):
			if g.ntiid == ntiid:
				idx = i
				break
		return idx

	def find_grade(self, username, grade):
		grades = self.get(username, ())
		idx = self.index(username, grade, grades)
		return grades[idx] if idx != -1 else None

	def add_grade(self, username, grade):
		grades = self.get(username, None)
		if grades is None:
			grades = self[username] = BList()

		adpated = grades_interfaces.IGrade(grade)
		idx = self.index(username, adpated, grades)
		locate(adpated, self, adpated.ntiid)
		if idx == -1:
			grades.append(adpated)
			notify(grades_interfaces.GradeAddedEvent(adpated, username))
		else:
			grades[idx] = adpated
			notify(grades_interfaces.GradeModifiedEvent(adpated, username))

	set_grade = add_grade

	def get_grades(self, username):
		grades = self.get(username, None)
		return list(grades) if grades else None

	def remove_grade(self, username, grade):
		grades = self.get(username, ())
		idx = self.index(username, grade, grades)
		if idx != -1:
			g = grades.pop(idx)
			notify(grades_interfaces.GradeRemovedEvent(g, username))
		return idx != -1

	def clear(self, username):
		grades = self.pop(username, None)
		return grades

	def clearAll(self):
		super(Grades, self).clear()

	def updateFromExternalObject(self, ext, *args, **kwargs):
		modified = False
		items = ext.get('Items', {})
		for username, grades in items.items():
			for grade_ext in grades:
				modified = True
				grade = internalization.find_factory_for(grade_ext)() 
				internalization.update_from_external_object(grade, grade_ext)
				self.set_grade(username, grade)
		return modified

