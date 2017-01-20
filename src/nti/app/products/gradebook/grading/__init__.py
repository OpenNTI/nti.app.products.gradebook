#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

#: [re]/export
from nti.app.products.gradebook.grading.interfaces import IGradeBookGradingPolicy

#: [re]/export
from nti.app.products.gradebook.grading.utils import PredictedGrade
from nti.app.products.gradebook.grading.utils import calculate_grades
from nti.app.products.gradebook.grading.utils import get_presentation_scheme
from nti.app.products.gradebook.grading.utils import calculate_predicted_grade

#: [re]/export
from nti.contenttypes.courses.grading import find_grading_policy_for_course

#: Current grade link/view
VIEW_CURRENT_GRADE = 'CurrentGrade'
