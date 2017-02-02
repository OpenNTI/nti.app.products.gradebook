#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

# disable: accessing protected members, too many methods
# pylint: disable=W0212,R0904

from hamcrest import is_
from hamcrest import contains
from hamcrest import has_length
from hamcrest import assert_that
from hamcrest import contains_inanyorder

import fudge

from unittest import TestCase

from zope.component import provideAdapter

from nti.app.products.gradebook.adapters import _as_course

from nti.app.products.gradebook.gradebook import GradeBook
from nti.app.products.gradebook.interfaces import IGradeBook

from nti.app.products.gradebook.grades import PredictedGrade

from nti.app.products.gradebook.views import _get_grade_parts
from nti.app.products.gradebook.views.summary_views import UserGradeSummary
from nti.app.products.gradebook.views.summary_views import GradeBookSummaryView

from nti.app.products.courseware.interfaces import ICourseInstance

from nti.contenttypes.courses.courses import CourseInstance

from nti.externalization.representation import WithRepr

from nti.app.testing.request_response import DummyRequest

@WithRepr
class MockGrade( object ):

	def __init__( self, value='0' ):
		self.value = value

@WithRepr
class MockSummary( UserGradeSummary ):
	"By default, every field is non-null at the start of ascending order."

	def __init__( self, alias='a', last_name='a', username='a',
					overdue_count=0, ungraded_count=0,
					grade_value=0, history_item=False,
					feedback_count=0, created_date=0,
					predicted_grade=None ):
		self.alias = alias
		self.last_name = last_name
		self.username = username
		self.overdue_count = overdue_count
		self.ungraded_count = ungraded_count
		self.grade_value = grade_value
		self.feedback_count = feedback_count
		self.history_item = history_item
		self.created_date = created_date
		self.predicted_grade = predicted_grade or PredictedGrade(correctness=0.0)

class TestGradeBookSummary( TestCase ):

	def setUp(self):
		provideAdapter( _as_course, adapts=(IGradeBook,), provides=ICourseInstance )

	def test_grade_parts(self):
		# Could be a lot of types: 7, 7/10, 95, 95%, A-, 90 A
		grade_val = _get_grade_parts( 100 )
		assert_that( grade_val, is_( (100,) ) )

		grade_val = _get_grade_parts( '20' )
		assert_that( grade_val, is_( (20,) ) )

		grade_val = _get_grade_parts( 98.6 )
		assert_that( grade_val, is_( (98.6,) ) )

		grade_val = _get_grade_parts( '98 -' )
		assert_that( grade_val, is_( (98, '-') ) )

		# We don't handle this yet.
		grade_val = _get_grade_parts( '90 A' )
		assert_that( grade_val, is_( (90, 'A') ) )

	@fudge.patch( 'pyramid.url.URLMethodsMixin.current_route_path' )
	@fudge.patch( 'nti.app.products.gradebook.views.summary_views.GradeBookSummaryView.final_grade_entry' )
	@fudge.patch( 'nti.app.products.gradebook.views.summary_views.GradeBookSummaryView.assignments' )
	def test_sorting( self, mock_url, mock_final_grade, mock_assignments ):
		"Test sorting/batching params of gradebook summary."
		mock_url.is_callable().returns( '/path/' )
		mock_final_grade.is_callable()
		mock_assignments.is_callable()
		request = DummyRequest( params={} )
		gradebook = GradeBook()
		gradebook.__parent__ = CourseInstance()
		view = GradeBookSummaryView( gradebook, request )
		do_sort = view._get_user_result_set

		# Empty
		result = do_sort( {}, () )
		assert_that( result, has_length( 0 ))

		# Single sort by final
		summary = MockSummary()
		summaries = ( summary, )
		request.params={ 'sortOn' : 'GRADE' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))

		# Single sort by alias
		request.params={ 'sortOn' : 'aliaS' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))
		assert_that( result, contains( summary ))

		# Single sort by something else, which defaults to last_name
		request.params={ 'sortOn' : 'XXX', 'sortOrder': 'ascending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))
		assert_that( result, contains( summary ))

		# Case insensitive numerical sort by grade
		summary2 = MockSummary()
		summary2.grade_value = '10'
		summary3 = MockSummary()
		summary3.grade_value = '90 -'
		summary4 = MockSummary()
		summary4.grade_value = '55 A'

		summaries = [ summary4, summary3, summary2, summary ]
		request.params={ 'sortOn' : 'gradE', 'sortOrder': 'ascending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary, summary2, summary4, summary3 ))

		# Reverse
		request.params={ 'sortOn' : 'gradE', 'sortOrder': 'descending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary3, summary4, summary2, summary ))

		# Sort by grade, history_item
		summary2 = MockSummary()
		summary2.grade_value = '100'
		summary2.history_item = False
		summary3 = MockSummary()
		summary3.grade_value = '100'
		summary3.history_item = True
		summary4 = MockSummary()
		summary4.history_item = True

		summaries = [ summary4, summary3, summary2, summary ]
		request.params={ 'sortOn' : 'gradE', 'sortOrder': 'descending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary3, summary2, summary4, summary ))

		# Sort by predicted_grade
		summary2 = MockSummary()
		summary2.predicted_grade = PredictedGrade(correctness=10)
		summary3 = MockSummary()
		summary3.predicted_grade = PredictedGrade(correctness=90)
		summary4 = MockSummary()
		summary4.predicted_grade = PredictedGrade(correctness=55)

		summaries = [ summary4, summary3, summary2, summary ]
		request.params={ 'sortOn' : 'PREDICTEDgradE', 'sortOrder': 'ascending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary, summary2, summary4, summary3 ))

		# Alias; desc
		summary2.alias = 'zzzz'
		summary3.alias = 'mmm'
		summary4.alias = None
		request.params={ 'sortOn' : 'ALIAS', 'sortOrder': 'descending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary2, summary3, summary, summary4 ))

		# Default; desc
		summary2.last_name = 'zzzz'
		summary3.last_name = 'mmm'
		summary4.last_name = None
		request.params={ 'sortOn' : 'XXX', 'sortOrder': 'descending' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary2, summary3, summary, summary4 ))

		# Username; ascending
		summary2.username = 'zzzz'
		summary3.username = 'mmm'
		summary4.username = None
		request.params={ 'sortOn' : 'username' }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 4 ))
		assert_that( result, contains( summary4, summary, summary3, summary2 ))

		# Same with batch
		request.params={ 'sortOn' : 'username', 'batchSize' : 1, 'batchStart' : 0 }
		result = do_sort( {}, summaries )
		assert_that( result, has_length( 1 ))
		assert_that( result, contains( summary4 ))

	@fudge.patch( 'nti.app.products.gradebook.views.summary_views.GradeBookSummaryView._get_enrollment_scoped_summaries' )
	@fudge.patch( 'nti.app.products.gradebook.views.summary_views.GradeBookSummaryView.final_grade_entry' )
	@fudge.patch( 'nti.app.products.gradebook.views.summary_views.GradeBookSummaryView.assignments' )
	def test_filtering( self, mock_get_students, mock_final_grade, mock_assignments ):
		"Test sorting/batching params of gradebook summary."
		mock_final_grade.is_callable()
		mock_assignments.is_callable()
		request = DummyRequest( params={} )
		gradebook = GradeBook()
		gradebook.__parent__ = CourseInstance()
		view = GradeBookSummaryView( gradebook, request )
		do_filter = view._do_get_user_summaries

		# Empty
		mock_get_students.is_callable().returns( () )
		result = do_filter()
		assert_that( result, has_length( 0 ))

		# Single with no filter
		summary = MockSummary()
		summaries = ( summary, )
		mock_get_students.is_callable().returns( summaries )
		result = do_filter()
		assert_that( list( result ), has_length( 1 ))

		# Single filter ungraded
		request.params={ 'filter' : 'UnGRADED' }
		result = do_filter()
		assert_that( list( result ), has_length( 0 ))

		# Single filter overdue
		request.params={ 'filter' : 'overDUE' }
		result = do_filter()
		assert_that( list( result ), has_length( 0 ))

		# actionable
		request.params={ 'filter' : 'actionablE' }
		result = do_filter()
		assert_that( list( result ), has_length( 0 ))

		# Multiple filters
		request.params={ 'filter' : 'actionablE,open' }
		result = do_filter()
		assert_that( list( result ), has_length( 0 ))

		# Multiple summaries/ filter ungraded
		summary2 = MockSummary()
		summary2.ungraded_count = 9
		summary3 = MockSummary()
		summary3.ungraded_count = 10
		summary4 = MockSummary()
		summary4.ungraded_count = 99

		summaries = [ summary4, summary3, summary2, summary ]
		mock_get_students.is_callable().returns( summaries )

		request.params={ 'filter' : 'ungraded,open' }
		result = do_filter()
		result = list( result )
		assert_that( result, has_length( 3 ))
		assert_that( result, contains_inanyorder( summary2, summary3, summary4 ))

		# Filter overdue
		summary2.overdue_count = 9
		summary3.overdue_count = 10
		summary4.overdue_count = 99
		request.params={ 'filter' : 'OVerDUE,open' }

		result = do_filter()
		result = list( result )
		assert_that( result, has_length( 3 ))
		assert_that( result, contains_inanyorder( summary2, summary3, summary4 ))

		# Actionable
		summary4.overdue_count = 0
		summary4.ungraded_count = 0
		request.params={ 'filter' : 'ACTIONAble,open' }

		result = do_filter()
		result = list( result )
		assert_that( result, has_length( 2 ))
		assert_that( result, contains_inanyorder( summary2, summary3 ))

	def test_searching( self ):
		"Test searching gradebook summary."
		request = DummyRequest( params={} )
		gradebook = GradeBook()
		gradebook.__parent__ = CourseInstance()
		view = GradeBookSummaryView( gradebook, request )
		do_search = view._search_summaries

		# Empty
		result = do_search( 'brasky', () )
		assert_that( result, has_length( 0 ))

		# Single with no match
		summary = MockSummary()
		summaries = ( summary, )
		result = do_search( 'brasky', summaries )
		assert_that( result, has_length( 0 ))

		# Multi with no match
		summary2 = MockSummary()
		summaries = ( summary, summary2 )
		result = do_search( 'brasky', summaries )
		assert_that( result, has_length( 0 ))

		# Four matches, case insensitive; matches
		# any part of field; multiple fields.
		summary = MockSummary()
		summary2 = MockSummary()
		summary3 = MockSummary()
		summary4 = MockSummary()
		summary.username = 'thisisbraskydotcom'
		summary2.alias = 'billbRASKy'
		summary3.last_name = 'brasky, william'
		summaries = ( summary, summary2, summary3, summary4 )

		result = do_search( 'brasky', summaries )
		assert_that( result, has_length( 3 ))
		assert_that( result,
					contains_inanyorder( summary, summary2, summary3 ))
