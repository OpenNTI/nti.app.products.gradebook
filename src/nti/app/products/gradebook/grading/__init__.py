#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

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
