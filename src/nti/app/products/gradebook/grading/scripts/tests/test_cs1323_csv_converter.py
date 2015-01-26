#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_not
from hamcrest import has_entry
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

import os
import unittest

from nti.app.products.gradebook.grading.policies import ICS1323CourseGradingPolicy
from nti.app.products.gradebook.grading.scripts.cs1323_csv_converter import process

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

from nti.testing.matchers import verifiably_provides, validly_provides

class TestCS1323CSVConverter(unittest.TestCase):
    
    layer = SharedConfiguringTestLayer
    
    def test_process(self):
        path = os.path.join( os.path.dirname(__file__), 'grading.csv')
        policy = process(path)
        assert_that(policy, validly_provides(ICS1323CourseGradingPolicy))
        assert_that(policy, verifiably_provides(ICS1323CourseGradingPolicy))

        assert_that(policy, has_property('categories', has_length(3)))
        assert_that(policy, has_property('categories', has_entry('turingscraft', has_length(4))))
        assert_that(policy, has_property('categories', has_entry('iclicker', has_length(8))))
        assert_that(policy, has_property('categories', has_entry('iclicker', has_length(8))))
        
        assert_that(policy, has_property('categories', 
                                         has_entry('iclicker', has_property('weight', 0.05))))
        assert_that(policy, has_property('categories', 
                                         has_entry('iclicker', has_property('dropLowest', 0))))
        
        assert_that(policy, has_property('categories', 
                                         has_entry('problets', has_property('weight', 0.0375))))