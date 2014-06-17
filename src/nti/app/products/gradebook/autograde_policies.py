#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Basic auto-grade policies.

.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import interface

from .interfaces import IPendingAssessmentAutoGradePolicy

@interface.implementer(IPendingAssessmentAutoGradePolicy)
class TrivialFixedScaleAutoGradePolicy(object):
	"""
	Scales each question equally, normalized to a particular value.
	If any part of a question is auto-assessed as incorrect, the entire
	question is graded as incorrect.

	We ignore the weight of parts.
	"""

	normalize_to = 20.0 # Magic value for the one class currently using this

	def autograde(self, item):
		# The UIs and/or some higher level ensure that we can never
		# submit an assignment that is missing any question sets,
		# or individual question parts. Therefore we can
		# assume we have the complete representation for scaling purposes.

		assessed_sum = 0.0
		theoretical_best = 0.0
		for assessed_set in item.parts:
			for assessed_question in assessed_set.questions:
				theoretical_best += 1.0 # scale to the number of questions
				part_sum = 0.0
				for assessed_part in assessed_question.parts:
					if not assessed_part.assessedValue:
						# WRONG part, whole question is toast
						part_sum = 0.0
						break
					part_sum += assessed_part.assessedValue
				# scale the parts to the whole question
				part_sum = part_sum / float(len(assessed_question.parts))
				# and finally count it for the question
				assessed_sum += part_sum


		# No submit part
		if not theoretical_best:
			return None

		# Each part was between 0 and 1. Now normalize
		as_percent = assessed_sum / theoretical_best
		return as_percent * self.normalize_to
