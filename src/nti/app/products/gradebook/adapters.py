#!/usr/bin/env python
# -*- coding: utf-8 -*
"""
gradebook externalization

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface
from zope import component

from . import grades
from . import interfaces as grade_interfaces

@interface.implementer(grade_interfaces.IGrade)
@component.adapter(basestring)
def _StringGradeAdapter(nttid):
	return grades.Grade(nttid=nttid)

@interface.implementer(grade_interfaces.IGrade)
@component.adapter(grade_interfaces.IGradeBookEntry)
def _EntryGradeAdapter(entry):
	return grades.Grade(nttid=entry.NTIID)
