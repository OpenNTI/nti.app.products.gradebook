#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Grades definition

$Id$
"""
from __future__ import unicode_literals, print_function, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface
from zope import lifecycleevent
from zope.location import locate
from zope.interface.common import mapping
from zope.annotation import factory as an_factory
from zope.container import contained as zcontained
from zope.annotation import interfaces as an_interfaces
from zope.mimetype import interfaces as zmime_interfaces

from zc.blist import BList

from persistent.mapping import PersistentMapping

from nti.contenttypes.courses import interfaces as course_interfaces

from nti.dataserver import mimetype
from nti.dataserver.datastructures import ModDateTrackingObject

from nti.externalization import externalization
from nti.externalization import interfaces as ext_interfaces
from nti.externalization.datastructures import LocatedExternalDict

from nti.utils.property import alias
from nti.utils.schema import SchemaConfigured
from nti.utils.schema import createDirectFieldProperties

from . import interfaces as grades_interfaces

@interface.implementer(grades_interfaces.IGrade,
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class Grade(ModDateTrackingObject, SchemaConfigured, zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	createDirectFieldProperties(grades_interfaces.IGrade)

	ntiid = alias('NTIID')

	def clone(self):
		result = self.__class__()
		result.__parent__, result.__name__ = (None, self.__name__)
		result.copy(self, False)
		return result

	def copy(self, other, parent=False):
		self.NTIID = other.NTIID
		self.grade = other.grade
		self.username = other.username
		if parent:
			self.__name__ = other.__name__
			self.__parent__ = other.__parent__
		self.updateLastMod()
		return self

	def __eq__(self, other):
		try:
			return self is other or (self.NTIID == other.NTIID
									 and self.username == other.username)
		except AttributeError:
			return NotImplemented

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.NTIID)
		xhash ^= hash(self.username)
		return xhash

	def __str__(self):
		return "%s,%s,%s" % (self.username, self.ntiid, self.grade)

	def __repr__(self):
		return "%s(%s,%s,%s)" % (self.__class__.__name__,
								 self.username,
								 self.NTIID,
								 self.grade)

def _indexof_grade(grade, grades):
	idx = -1
	ntiid = getattr(grade, 'NTIID', unicode(grade))
	for i, g in enumerate(grades):
		if g.NTIID == ntiid:
			idx = i
			break
	return idx

@interface.implementer(mapping.IReadMapping, ext_interfaces.IExternalizedObject)
class _UserGradesResource(zcontained.Contained):

	__slots__ = ('blist', 'username', '__name__', '__parent__')

	def __init__(self, obj, username):
		self.blist = obj
		self.username = username

	def __getitem__(self, key):
		idx = _indexof_grade(key, self.blist)
		if idx != -1:
			return self.blist[idx]
		raise KeyError(key)

	def __contains__(self, key):
		idx = _indexof_grade(key, self.blist)
		return idx != -1
	
	def get(self, key, default=None):
		try:
			result = self.__getitem__(key)
		except KeyError:
			result = default
		return result

	def ntiids(self):
		result = tuple((g.NTIID for g in self.blist))
		return result
	keys = ntiids

	def values(self):
		return self.blist

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.username)
		return xhash

	def toExternalObject(self):
		result = LocatedExternalDict({'username':self.username})
		items = result['Items'] = []
		for grade in self.values():
			ext = externalization.to_external_object(grade)
			items.append(ext)
		return result

@component.adapter(course_interfaces.ICourseInstance)
@interface.implementer(grades_interfaces.IGrades, 
					   an_interfaces.IAttributeAnnotatable,
					   zmime_interfaces.IContentTypeAware)
class Grades(PersistentMapping, ModDateTrackingObject, zcontained.Contained):

	__metaclass__ = mimetype.ModeledContentTypeAwareRegistryMetaclass

	__super_getitem = PersistentMapping.__getitem__
	
	def index(self, grade, username=None, grades=None):
		username = username or getattr(grade, 'username', None)
		grades = grades if grades is not None else self.get_grades(username, ())
		idx = _indexof_grade(grade, grades)
		return idx

	def find_grade(self, grade, username=None):
		username = username or getattr(grade, 'username', None)
		grades = self.get_grades(username, ())
		idx = self.index(grade, username, grades)
		return grades[idx] if idx != -1 else None

	def add_grade(self, grade, username=None):
		username = username or grade.username
		grades = self.get_grades(username, None)
		if grades is None:
			grades = self[username] = BList()

		grade.username = username # make sure it has the same username
		if grade.__parent__ is None:
			locate(grade, self, grade.ntiid)

		idx = self.index(grade, username, grades)
		if idx == -1:
			grades.append(grade)
			idx = len(grades) - 1
			lifecycleevent.added(grade)
		else:
			modified = grades[idx]
			modified.copy(grade, False)
			modified.updateLastMod()
			lifecycleevent.modified(modified)

		self.updateLastMod()
		return idx

	set_grade = add_grade

	def remove_grade(self, grade, username=None):
		username = username or getattr(grade, 'username', None)
		grades = self.get_grades(username, ())
		idx = self.index(grade, username, grades)
		if idx != -1:
			g = grades.pop(idx)
			lifecycleevent.removed(g)
			self.updateLastMod()
		return idx != -1

	def remove_grades(self, ntiid):
		for username in self.keys():
			self.remove_grade(ntiid, username)
			
	def clear(self, username):
		grades = self.pop(username, None)
		for grade in grades or ():
			lifecycleevent.removed(grade)
		self.updateLastMod()
		return True if grades else False

	def clearAll(self):
		for username in list(self.keys()):
			self.clear(username)

	def __getitem__(self, username):
		grades = self.__super_getitem(username)
		result = _UserGradesResource(grades, username)
		result.__parent__ = self
		return result

	def get_grades(self, username, default=None):
		try:
			grades = self.__super_getitem(username)
			return grades
		except KeyError:
			return default

	def __hash__(self):
		xhash = 47
		xhash ^= hash(self.__name__)
		return xhash

_GradesFactory = an_factory(Grades, 'Grades')
