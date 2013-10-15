#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from .. import gradebook
from .. import interfaces as grades_interfaces

from nti.testing.base import SharedConfiguringTestBase
from nti.testing.matchers import verifiably_provides, validly_provides

from hamcrest import assert_that

class TestGradeBook(SharedConfiguringTestBase):

    set_up_packages = ('nti.dataserver', 'nti.app.products.gradebook')

    def test_interfaces(self):
        gb = gradebook.GradeBook()
        assert_that(gb, validly_provides(grades_interfaces.IGradeBook))
        assert_that(gb, verifiably_provides(grades_interfaces.IGradeBook))
