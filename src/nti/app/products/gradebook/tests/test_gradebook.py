#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from .. import gradebook
from .. import interfaces as grades_interfaces

from .  import ConfiguringTestBase

from nti.testing.matchers import verifiably_provides, validly_provides

from hamcrest import assert_that

class TestGradeBook(ConfiguringTestBase):

    def test_interfaces(self):
        gb = gradebook.GradeBook()
        assert_that(gb, validly_provides(grades_interfaces.IGradeBook))
        assert_that(gb, verifiably_provides(grades_interfaces.IGradeBook))

        gbp = gradebook.GradeBookPart()
        gbp.order = 1
        gbp.__name__ = gbp.name = 'part'
        assert_that(gbp, validly_provides(grades_interfaces.IGradeBookPart))
        assert_that(gbp, verifiably_provides(grades_interfaces.IGradeBookPart))

        gbe = gradebook.GradeBookEntry()
        gbe.order = 1
        gbe.__name__ = gbe.name = 'entry'
        assert_that(gbe, validly_provides(grades_interfaces.IGradeBookEntry))
        assert_that(gbe, verifiably_provides(grades_interfaces.IGradeBookEntry))
