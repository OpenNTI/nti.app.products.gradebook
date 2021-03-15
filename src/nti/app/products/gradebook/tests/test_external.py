#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, absolute_import, division

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import none
from hamcrest import is_not
from hamcrest import not_none
from hamcrest import has_entry
from hamcrest import assert_that
from hamcrest import has_property
does_not = is_not

import unittest

from nti.app.products.gradebook.gradebook import GradeBook
from nti.app.products.gradebook.gradebook import GradeBookPart
from nti.app.products.gradebook.gradebook import GradeBookEntry

from nti.app.products.gradebook.grades import PersistentGrade as Grade

from nti.app.products.gradebook.gradescheme import LetterGradeScheme
from nti.app.products.gradebook.gradescheme import BooleanGradeScheme
from nti.app.products.gradebook.gradescheme import IntegerGradeScheme
from nti.app.products.gradebook.gradescheme import NumericGradeScheme

from nti.dataserver.users.users import User

from nti.externalization import externalization
from nti.externalization import internalization

from nti.app.products.gradebook.tests import SharedConfiguringTestLayer

from nti.dataserver.tests.mock_dataserver import WithMockDSTrans


class TestExternal(unittest.TestCase):

    layer = SharedConfiguringTestLayer

    def _create_user(self, username=u'nt@nti.com', password=u'temp001'):
        usr = User.create_user(self.ds, username=username, password=password)
        return usr

    def test_grade(self):
        g = Grade(username=u'nt@nti.com', grade=85.0)
        ext = externalization.to_external_object(g)
        assert_that(ext, has_entry('Class', 'Grade'))
        assert_that(ext, has_entry('value', is_(85.0)))
        assert_that(ext, has_entry('Username', 'nt@nti.com'))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.grade'))
        assert_that(ext, has_entry('Last Modified', is_not(none())))

        factory = internalization.find_factory_for(ext)
        newgrade = factory()
        newgrade.__parent__ = GradeBookEntry()

        internalization.update_from_external_object(newgrade, ext)
        assert_that(newgrade, has_property('value', is_(85.0)))
        assert_that(newgrade, has_property('Username', is_('nt@nti.com')))

    def test_notable_grade(self):
        newgrade = Grade(username=u'nt@nti.com', grade=85.0)
        newgrade.__parent__ = entry = GradeBookEntry()
        entry.AssignmentId = u'assignment_id'
        ext = externalization.to_external_object(newgrade, name='live_notable', decorate=False)
        assert_that(ext, has_entry('Class', 'Grade'))
        assert_that(ext, has_entry('Username', 'nt@nti.com'))
        assert_that(ext, has_entry('AssignmentId', 'assignment_id'))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.grade'))
        assert_that(ext, has_entry('Last Modified', is_not(none())))
        assert_that(ext, does_not(has_entry('value', is_(85.0))))

    @WithMockDSTrans
    def test_gradebook(self):
        class Parent(object):
            __parent__ = None
            __name__ = u'CS1330'

        gb = GradeBook()
        gb.__parent__ = Parent()
        gb.creator = self._create_user()

        ext = externalization.to_external_object(gb)
        assert_that(ext, has_entry('Class', 'GradeBook'))
        assert_that(ext, has_entry('CreatedTime', is_not(none())))
        assert_that(ext, has_entry('Creator', 'nt@nti.com'))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.gradebook'))

    @WithMockDSTrans
    def test_gradebookpart(self):

        gb = GradeBook()

        gbp = GradeBookPart()
        gbp.__parent__ = gb
        gbp.Name = u'quizzes'
        gbp.order = 1
        gbp.displayName = u'Quizzes'
        #gbp.weight = 0.95

        ext = externalization.to_external_object(gbp)
        assert_that(ext, has_entry('Class', 'GradeBookPart'))
        assert_that(ext, has_entry('CreatedTime', is_not(none())))
        assert_that(ext, has_entry('Name', 'quizzes'))
        assert_that(ext, has_entry('order', 1))
        # assert_that(ext, has_entry(u'weight', 0.95))
        assert_that(ext, has_entry('displayName', 'Quizzes'))
        # assert_that(ext, has_entry(u'TotalEntryWeight', 0.0))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.gradebookpart'))

    @WithMockDSTrans
    def test_gradebookentry(self):

        gbp = GradeBookPart()
        gbp.__name__ = u'quizzes'

        gbe = GradeBookEntry()
        gbe.__parent__ = gbp
        gbe.order = 2
        gbe.Name = u'quiz1'
        # gbe.weight = 0.55
        gbe.displayName = u'Quiz 1'
        gbe.assignmentId = u'myquestion'

        ext = externalization.to_external_object(gbe)
        assert_that(ext, has_entry('Class', 'GradeBookEntry'))
        assert_that(ext, has_entry('Name', 'quiz1'))
        assert_that(ext, has_entry('order', 2))
        # assert_that(ext, has_entry(u'weight', 0.55))
        assert_that(ext, has_entry('displayName', 'Quiz 1'))
        assert_that(ext, has_entry('DueDate', is_(none())))
        assert_that(ext, has_entry('GradeScheme', is_(none())))
        assert_that(ext, has_entry('AssignmentId', 'myquestion'))
        assert_that(ext, has_entry('CreatedTime', is_not(none())))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.gradebookentry'))

    @WithMockDSTrans
    def test_gradescheme(self):
        s = BooleanGradeScheme()
        ext = externalization.to_external_object(s)
        assert_that(ext, has_entry('Class', 'BooleanGradeScheme'))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.gradebook.booleangradescheme'))

        s = IntegerGradeScheme()
        ext = externalization.to_external_object(s)
        assert_that(ext, has_entry('Class', 'IntegerGradeScheme'))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.gradebook.integergradescheme'))
        assert_that(ext, has_entry('min', 0))
        assert_that(ext, has_entry('max', 100))

        s = NumericGradeScheme(min=10.0, max=15.0)
        ext = externalization.to_external_object(s)
        assert_that(ext, has_entry('Class', 'NumericGradeScheme'))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.gradebook.numericgradescheme'))
        assert_that(ext, has_entry('min', 10.0))
        assert_that(ext, has_entry('max', 15.0))

        scheme = internalization.find_factory_for(ext)()
        internalization.update_from_external_object(scheme, ext)
        assert_that(s, is_(scheme))

        s = LetterGradeScheme()
        ext = externalization.to_external_object(s)
        assert_that(ext, has_entry('Class', 'LetterGradeScheme'))
        assert_that(ext,
                    has_entry('MimeType', 'application/vnd.nextthought.gradebook.lettergradescheme'))
        assert_that(ext, has_entry('grades', is_(['A', 'B', 'C', 'D', 'F'])))
        assert_that(ext,
                    has_entry('ranges', is_([[90, 100], [80, 89], [70, 79], [40, 69], [0, 39]])))

        scheme = internalization.find_factory_for(ext)()
        internalization.update_from_external_object(scheme, ext)
        assert_that(s, is_(scheme))
        assert_that(s, has_property('grades', is_(('A', 'B', 'C', 'D', 'F'))))
        assert_that(s,
                    has_property('ranges', is_(((90, 100), (80, 89), (70, 79), (40, 69), (0, 39)))))
