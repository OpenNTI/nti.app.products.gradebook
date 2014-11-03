#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from nti.dataserver.interfaces import INotableFilter

from .interfaces import IGrade

@interface.implementer( INotableFilter )
class AssignmentGradeNotableFilter(object):
	"""
	Determines if an assignment grade is notable for the given user.
	"""
	def __init__(self, context):
		self.context = context

	def is_notable(self, obj, user):
		return IGrade.providedBy(obj) and obj.Username == user.username
