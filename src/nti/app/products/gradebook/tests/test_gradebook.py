#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

# pylint: disable=protected-access,too-many-public-methods

from hamcrest import is_
from hamcrest import is_in
from hamcrest import is_not
from hamcrest import has_key
from hamcrest import assert_that
does_not = is_not

from nti.testing.matchers import validly_provides
from nti.testing.matchers import verifiably_provides

import unittest

from nti.app.products.gradebook.gradebook import GradeBook
from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.interfaces import IGradeBook
from nti.app.products.gradebook.interfaces import IGradeBookPart
from nti.app.products.gradebook.interfaces import IGradeBookEntry

from nti.app.products.gradebook.grades import PersistentGrade as Grade

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer


class TestGradebook(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def test_interfaces(self):
        gb = GradeBook()
        assert_that(gb, validly_provides(IGradeBook))
        assert_that(gb, verifiably_provides(IGradeBook))

        gbp = GradeBookPart()
        gbp.order = 1
        gbp.__parent__ = gb
        gbp.__name__ = gbp.displayName = u'part'
        assert_that(gbp, validly_provides(IGradeBookPart))
        assert_that(gbp, verifiably_provides(IGradeBookPart))

        gbe = GradeBookEntry()
        gbe.order = 1
        gbe.__parent__ = gbp
        gbe.assignmentId = u'xzy'
        gbe.__name__ = gbe.displayName = u'entry'
        assert_that(gbe, validly_provides(IGradeBookEntry))
        assert_that(gbe, verifiably_provides(IGradeBookEntry))

    def test_gradebook_entry_case_insensitive_for_contains(self):
        # Because it should be case insensitive for everything,
        # but we have existing objects that aren't. Sigh.
        gbe = GradeBookEntry()
        grade = Grade()

        gbe['key'] = grade
        assert_that('KEY', is_in(gbe))

        assert_that(gbe.get('KEY'), is_(grade))
        assert_that(gbe.__getitem__('KEY'), is_(grade))

    def test_gradebook_delete(self):
        book = GradeBook()

        part = GradeBookPart()
        part.order = 1
        part.displayName = u'part'
        book['part'] = part

        entry = GradeBookEntry()
        entry.order = 1
        entry.assignmentId = u'xzy'
        entry.displayName = u'entry'
        part['entry'] = entry

        grade = Grade()
        entry['ichigo'] = grade

        assert_that(entry, has_key('ichigo'))
        assert_that(list(part.iter_usernames()), is_(['ichigo']))
        assert_that(list(book.iter_usernames()), is_(['ichigo']))

        book.remove_user('ichigo')
        assert_that(entry, does_not(has_key('ichigo')))
        assert_that(list(part.iter_usernames()), is_([]))
        assert_that(list(book.iter_usernames()), is_([]))
