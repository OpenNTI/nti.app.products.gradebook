#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Views and other functions related to grades and gradebook.

$Id$
"""
from __future__ import print_function, unicode_literals, absolute_import, division
__docformat__ = "restructuredtext en"

logger = __import__('logging').getLogger(__name__)

from zope import component
from zope import interface
from zope.traversing.interfaces import IPathAdapter

from pyramid.view import view_config
from pyramid.interfaces import IRequest
from pyramid import httpexceptions as hexc

from nti.app.base.abstract_views import AbstractAuthenticatedView
from nti.app.externalization.view_mixins import ModeledContentEditRequestUtilsMixin
from nti.app.externalization.view_mixins import ModeledContentUploadRequestUtilsMixin

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver import authorization as nauth

from nti.dataserver.users.interfaces import IUserProfile
import nameparser

from ..interfaces import IGrade
from ..interfaces import IGradeBook
from ..interfaces import ISubmittedAssignmentHistoryBase

@interface.implementer(IPathAdapter)
@component.adapter(ICourseInstance, IRequest)
def GradeBookPathAdapter(context, request):
	result = IGradeBook(context)
	return result

@view_config(route_name='objects.generic.traversal',
			 permission=nauth.ACT_UPDATE,
			 renderer='rest',
			 context=IGrade,
			 request_method='PUT')
class GradePutView(AbstractAuthenticatedView,
				   ModeledContentUploadRequestUtilsMixin,
				   ModeledContentEditRequestUtilsMixin):

	content_predicate = IGrade.providedBy

	def _do_call(self):
		theObject = self.request.context
		self._check_object_exists(theObject)
		self._check_object_unmodified_since(theObject)

		externalValue = self.readInput()
		self.updateContentObject(theObject, externalValue)
		theObject.updateLastMod()

		# Now, because grades are not persistent objects,
		# the btree bucket containing this grade has to be
		# manually told that its contents have changed.
		# XXX: Note that this is very expensive,
		# waking up each bucket of the tree.

		column = theObject.__parent__
		btree = column._SampleContainer__data
		bucket = btree._firstbucket
		found = False
		while bucket is not None:
			if bucket.has_key(theObject.__name__):
				bucket._p_changed = True
				if bucket._p_jar is None: # The first bucket is stored special
					btree._p_changed = True
				found = True
				break
			bucket = bucket._next
		if not found:
			# before there are buckets, it might be inline data?
			btree._p_changed = True

		return theObject


from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory
from nti.assessment.assignment import QAssignmentSubmissionPendingAssessment
from nti.assessment.submission import AssignmentSubmission
from nti.dataserver.users import User
from nti.app.products.courseware.interfaces import ICourseInstanceActivity

@view_config(route_name='objects.generic.traversal',
			 permission=nauth.ACT_UPDATE,
			 renderer='rest',
			 context='nti.app.products.gradebook.gradebook.GradeWithoutSubmission',
			 request_method='PUT')
class GradeWithoutSubmissionPutView(GradePutView):
	"Called to put to a grade that doesn't yet exist."

	#: We don't want extra catching of key errors
	_EXTRA_INPUT_ERRORS = ()

	def _do_call(self):
		# So we make one exist
		entry = self.request.context.__parent__
		username = self.request.context.__name__

		user = User.get_user(username)
		# canonicalize the username in the event case got mangled
		username = user.username
		assignmentId = entry.AssignmentId

		# We insert the history item, which the user himself
		# normally does but cannot in this case. This implicitly
		# creates the grade
		# TODO: This is very similar to what nti.app.assessment.adapters
		# does for the student, just with fewer constraints...
		submission = AssignmentSubmission()
		submission.assignmentId = assignmentId
		submission.creator = user

		pending_assessment = QAssignmentSubmissionPendingAssessment( assignmentId=submission.assignmentId,
																	 parts=[] )
		course = ICourseInstance(entry)

		assignment_history = component.getMultiAdapter( (course, submission.creator),
														IUsersCourseAssignmentHistory )

		assignment_history.recordSubmission( submission, pending_assessment )

		# We don't want this phony-submission showing up as course activity
		# See nti.app.assessment.subscribers
		activity = ICourseInstanceActivity(course)
		activity.remove(submission)


		# This inserted the 'real' grade. To actually
		# updated it with the given values, let the super
		# class do the work
		self.request.context = entry[username]

		return super(GradeWithoutSubmissionPutView,self)._do_call()

from nti.externalization.oids import to_external_ntiid_oid
from nti.externalization.interfaces import LocatedExternalDict
from nti.contenttypes.courses.interfaces import is_instructed_by_name
from nti.dataserver.interfaces import IEnumerableEntityContainer
from nti.contenttypes.courses.interfaces import ICourseEnrollments
from nti.dataserver.users import Entity
from nti.dataserver.users.interfaces import IFriendlyNamed
from nti.appserver.interfaces import IIntIdUserSearchPolicy
from nti.app.externalization.view_mixins import BatchingUtilsMixin
from nti.dataserver.interfaces import IUser
from natsort import natsorted

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=ISubmittedAssignmentHistoryBase,
			 permission=nauth.ACT_READ)
class SubmittedAssignmentHistoryGetView(AbstractAuthenticatedView,
										BatchingUtilsMixin):
	"""
	Support retrieving the submitted assignment history (and summaries)
	typically for a particular column of the gradebok.

	The return dictionary will have the following entries:

	Items
		A dictionary from student username to submission history item
		(or possibly null)

	FilteredTotalItemCount
		The total number of items that match the filter, if specified;
		identical to TotalItemCount if there is no filter.

	TotalItemCount
		How many total submissions there are. If any filter, sorting
		or paging options are specified, this will be the same as the
		number of enrolled students in the class (because we will
		ultimately return that many rows due to the presence of null
		rows for non-submitted students).

	TotalNonNullItemCount
		How many total submissions there are. This does not depend
		on the presence of any filter, sort, or paging options.

	The following query parameters are supported:

	sortOn
		The field to sort on. Options are ``realname`` to sort on the parts
		of the user's realname ("lastname" first; note that this is
		imprecise and likely to sort non-English names incorrectly.);
		``dateSubmitted``; ``feedbackCount``; ``gradeValue``; ``username``.
		Note that if you sort, the Items dictionary becomes an ordered
		list of pairs. Also note that sorting by gradeValue may not have
		the expected results, depending on what sort of grade values are
		being used; we do our best.

	sortOrder
		The sort direction. Options are ``ascending`` and
		``descending``. If you do not specify, a value that makes the
		most sense for the ``sortOn`` parameter will be used by
		default.

	filter
		Whether to filter the returned data in some fashion. Several
		values are defined:

		* ``LegacyEnrollmentStatusForCredit``: Only students that are
		  enrolled for credit are returned. An entry in the dictionary is
		  returned for each such student, even if they haven't submitted;
		  the value for students that haven't submitted is null.

		* ``LegacyEnrollmentStatusOpen``: Only students that are
		  enrolled NOT for credit are returned. An entry in the dictionary is
		  returned for each such student, even if they haven't submitted;
		  the value for students that haven't submitted is null.

	batchSize
		Integer giving the page size. Must be greater than zero.
		Paging only happens when this is supplied together with
		``batchStart`` (or ``batchAround`` for those views that support it).

	batchStart
		Integer giving the index of the first object to return,
		starting with zero. Paging only happens when this is
		supplied together with ``batchSize``.

	batchAround
		String parameter giving the ``OID`` of an object to build a
		batch (page) around. When you give this parameter,
		``batchStart`` is ignored and the found object is centered at
		one-half the ``batchSize`` in the returned page---assuming
		there are enough following objects). If there are very few
		matching objects, and/or the ``batchSize`` is small, then the
		object may not be centered, but we do guarantee it will be in
		the returned values. If the object is not found (after all the
		filters are applied) then an empty batch is returned. (Even if
		you supply this value, you should still supply a value for
		``batchStart`` such as 1).

	batchAroundCreator
		String parameter giving the ``Creator`` of an object to build a batch (page)
		around. Otherwise identical to ``batchAround``.

	usernameSearchTerm
		If provided, only users that match this search term
		will be returned. This search is based on the username and
		realname and alias, and does prefix matching, the same as
		the normal search algorithm for users. This is independent
		of filtering.
	"""

	_BATCH_LINK_DROP_PARAMS = BatchingUtilsMixin._BATCH_LINK_DROP_PARAMS + ('batchAroundCreator',)

	def __call__(self):
		request = self.request
		context = request.context
		username = request.authenticated_userid
		course = ICourseInstance(context)

		if not is_instructed_by_name(course, username):
			raise hexc.HTTPForbidden()

		result = LocatedExternalDict()
		column = context.__parent__
		result.__parent__ = column
		result.__name__ = context.__name__

		filter_name = self.request.params.get('filter')
		sort_name = self.request.params.get('sortOn')
		username_search_term = self.request.params.get('usernameSearchTerm')
		if filter_name in ('LegacyEnrollmentStatusForCredit', 'LegacyEnrollmentStatusOpen'):
			# Get the set of usernames. Right now, we have a direct
			# dependency on the legacy course instance, so we need some better
			# abstractions around this. This will break when we have
			# non-legacy courses
			everyone = course.legacy_community
			restricted_id = course.LegacyScopes['restricted']
			restricted = Entity.get_entity(restricted_id) if restricted_id else None

			restricted_usernames = set(IEnumerableEntityContainer(restricted).iter_usernames()) if restricted is not None else set()
			everyone_usernames = set(IEnumerableEntityContainer(everyone).iter_usernames())
			# instructors are also a member of the restricted set,
			# so take them out (otherwise the count will be wrong)
			if filter_name == 'LegacyEnrollmentStatusForCredit':
				filter_usernames = restricted_usernames - {x.id for x in course.instructors}
			elif filter_name == 'LegacyEnrollmentStatusOpen':
				filter_usernames = everyone_usernames - restricted_usernames - {x.id for x in course.instructors}

			result['TotalItemCount'] = ICourseEnrollments(course).count_enrollments()
			result['FilteredTotalItemCount'] = len(filter_usernames)

			if username_search_term:
				policy = component.getAdapter(self.remoteUser, IIntIdUserSearchPolicy, name='comprehensive')
				matched_unames = [x.username for x in policy.query(username_search_term.lower(),
																   provided=IUser.providedBy)]
				filter_usernames = {x for x in filter_usernames if x in matched_unames}
				result['FilteredTotalItemCount'] = len(filter_usernames)


			# Because the items() method returns things in the order that they are
			# listed in usernames, we can sort usernames first to get the correct
			# order. This is especially helpful when paging as we can consume the part
			# of the generator needed.
			items_factory = dict # don't use an ordered dict if we don't sort
			items_iter = None
			sort_reverse = self.request.params.get('sortOrder', 'ascending') == 'descending'
			if sort_name == 'realname':
				# An alternative way to do this would be to get the
				# intids of the users (available from the EntityContainer)
				# and then have an index on the reverse name in the entity
				# catalog (we have the name parts, but keyword indexes are
				# not sortable)
				def _key(username):
					user = Entity.get_entity(username)
					if user is None: # deleted
						return username
					parts = IFriendlyNamed(user).get_searchable_realname_parts()
					if not parts:
						return username

					parts = reversed(parts) # last name first
					return ' '.join(parts).lower()

				filter_usernames = sorted(filter_usernames,
										  key=_key,
										  reverse=sort_reverse)
				items_factory = list
				items_iter = context.items(usernames=filter_usernames,placeholder=None)
			elif sort_name == 'username':
				filter_usernames = sorted(filter_usernames,
										  reverse=sort_reverse)
				items_factory = list
				items_iter = context.items(usernames=filter_usernames,placeholder=None)
			elif sort_name == 'dateSubmitted':
				filter_usernames = sorted(filter_usernames)
				all_items = context.items(usernames=filter_usernames,placeholder=None)
				items_iter = sorted(all_items,
									key=lambda x: x[1].createdTime if x[1] else 0,
									reverse=sort_reverse)
				items_factory = list
			elif sort_name == 'feedbackCount':
				filter_usernames = sorted(filter_usernames)
				all_items = context.items(usernames=filter_usernames,placeholder=None)
				items_iter = sorted(all_items,
									key=lambda x: x[1].FeedbackCount if x[1] else 0,
									reverse=sort_reverse)
				items_factory = list
			elif sort_name == 'gradeValue':
				filter_usernames = sorted(filter_usernames)
				all_items = context.items(usernames=filter_usernames,placeholder=None)
				items_iter = natsorted(all_items,
									   key=lambda x: IGrade(x[1]).value if x[1] else 0, # this is pretty inefficient
									   )
				if sort_reverse:
					items_iter = reversed(items_iter)
				items_factory = list
			elif sort_name: # pragma: no cover
				# We're not silently ignoring because in the past
				# we've had clients send in the wrong value for a long time
				# before anybody noticed
				raise hexc.HTTPBadRequest("Unsupported sort option")
			else:
				items_iter = context.items(usernames=filter_usernames,placeholder=None)

			batch_size, batch_start = self._get_batch_size_start()
			batchAround = None
			batchAroundKey = None
			# TODO: Similar to code in ugd_query_views
			if batch_size is not None:
				if self.request.params.get( 'batchAround', '' ):
					batchAround = self.request.params.get( 'batchAround' )
					batchAroundKey = lambda key_value: to_external_ntiid_oid( key_value[1] )
				elif self.request.params.get( 'batchAroundCreator', ''):
					# This branch we could optimize based on the usernames array above
					batchAround = self.request.params.get('batchAroundCreator').lower()
					batchAroundKey = lambda key_value: key_value[0].lower()

			if batchAround is not None:
				items_factory = list
				# Ok, they have requested that we compute a beginning index for them.
				# We do this by materializing the list in memory and walking through
				# to find the index of the requested object.
				batch_start = None # ignore input
				result_list = []
				match_index = None
				for i, key_value in enumerate(items_iter):
					result_list.append( key_value )

					# Only keep testing until we find what we need
					# TODO: We should be able to break under some
					# circumstances, yes? If the items_iter is a generator,
					# that would be benificial
					if batch_start is None:
						if batchAroundKey( key_value ) == batchAround:
							batch_start = max( 0, i - (batch_size // 2) - 1 )
							match_index = i

				items_iter = result_list
				if batch_start is None:
					# Well, we got here without finding the matching value.
					# So return an empty page.
					batch_start = len(result_list)
				elif match_index <= batch_start + batch_size:
					# For very small batches, when the match is at
					# the beginning of the list (typically),
					# we could wind up returning a list that doesn't include
					# the around value. Do our best to make sure that
					# doesn't happen.
					batch_start = max( 0, match_index - (batch_size // 2))
			if (batch_size is not None and batch_start is not None) or items_factory is list:
				self._batch_tuple_iterable(result, items_iter,
										   batch_size=batch_size,
										   batch_start=batch_start,
										   selector=lambda x: x)
			else:
				result['Items'] = items_factory(items_iter)

		else:
			# Everything
			result['Items'] = dict(context)
			result['TotalItemCount'] = len(result['Items'])
			result['FilteredTotalItemCount'] = result['TotalItemCount']

		result['TotalNonNullItemCount'] = len(context)

		return result

from nti.appserver.ugd_edit_views import UGDDeleteView
from zope.annotation import IAnnotations
from zope import lifecycleevent

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='DELETE',
			 context=IGradeBook,
			 permission=nauth.ACT_DELETE)
class GradebookDeleteView(UGDDeleteView):
	"""
	Admins can delete an entire gradebook. This is mostly
	for migration purposes from old databases.
	"""

	def _do_delete_object(self, context):
		# We happen to know that it is stored as
		# an annotation.

		annots = IAnnotations(context.__parent__)
		del annots[context.__name__]
		lifecycleevent.removed(context)

		return True

import csv
import collections
from nti.externalization.interfaces import LocatedExternalList
from cStringIO import StringIO
from nti.app.products.courseware.interfaces import ICourseInstanceEnrollment
from ..interfaces import NO_SUBMIT_PART_NAME

@view_config(route_name='objects.generic.traversal',
			 renderer='rest',
			 request_method='GET',
			 context=IGradeBook,
			 permission=nauth.ACT_READ,
			 name='contents.csv')
class GradebookDownloadView(AbstractAuthenticatedView):
	"""
	Provides a downloadable table of all the assignments
	present in the gradebook. There is a column
	for each assignment and a row for each user.

	A query param `LegacyEnrollmentStatus` can be set to
	either 'ForCredit' or 'Open' to restrict the results to that
	subset of students.

	.. note:: This is hardcoded to export in D2L compatible format.
		(https://php.radford.edu/~knowledge/lore/attachment.php?id=57)
		Dialects would be easily possible.
	"""

	def _make_enrollment_predicate(self):
		status_filter = self.request.GET.get('LegacyEnrollmentStatus')
		if not status_filter:
			return lambda course, user: True

		def f(course,user):
			enrollment = component.getMultiAdapter((course, user),
												   ICourseInstanceEnrollment)
			return enrollment.LegacyEnrollmentStatus == status_filter # Let this blow up when this goes away
		return f

	def __call__(self):
		gradebook = self.request.context
		course = ICourseInstance(gradebook)
		predicate = self._make_enrollment_predicate()

		# We build a dictionary of {username: {Assignment: Grade} }
		# We keep track of known assignment names so we can sort appropriately

		usernames_to_assignment_dict = collections.defaultdict(dict)
		seen_asg_names = set()

		final_grade_entry = None

		for part in gradebook.values():
			for name, entry in part.items():
				if part.__name__ == NO_SUBMIT_PART_NAME and name == 'Final Grade':
					final_grade_entry = entry
					continue

				seen_asg_names.add(name)
				for username, grade in entry.items():
					user_dict = usernames_to_assignment_dict[username]
					if name in user_dict:
						raise ValueError("Two entries in different part with same name, yikes")
					user_dict[name] = grade

		sorted_asg_names = sorted(seen_asg_names)

		# Now we can build up the rows.
		rows = LocatedExternalList()
		rows.__name__ = self.request.view_name
		rows.__parent__ = self.request.context

		# First a header row.
		# Note that we are allowed to use multiple columns to identify
		# students
		rows.append( ['Username', 'First Name', 'Last Name', 'Full Name']
					 + [x + ' Points Grade' for x in sorted_asg_names]
					 + ['Adjusted Final Grade Numerator', 'Adjusted Final Grade Denominator']
					 + ['End-of-Line Indicator'] )

		# Now a row for each user and each assignment in the same order.
		# Note that the webapp tends to send string values even when the user
		# typed a number: "75 -". For export purposes, if we can reverse that to a number,
		# we want it to be a number.
		def _tx(value):
			if not isinstance(value, basestring):
				return value
			if value.endswith(' -'):
				try:
					return int(value[:-2])
				except ValueError:
					try:
						return float(value[:-2])
					except ValueError:
						return value

		for username, user_dict in sorted(usernames_to_assignment_dict.items()):
			user = User.get_user(username)
			if not user or not predicate(course,user):
				continue

			profile = IUserProfile(user)
			realname = profile.realname or ''
			if realname and '@' not in realname and realname != username:
				human_name = nameparser.HumanName( realname )
				firstname = human_name.first or ''
				lastname = human_name.last or ''
			else:
				firstname = ''
				lastname = ''

			row = [username, firstname, lastname, realname]
			for assignment in sorted_asg_names:
				grade = user_dict[assignment].value if assignment in user_dict else ""
				row.append(_tx(grade))

			final_grade = final_grade_entry.get(username) if final_grade_entry else None
			row.append(_tx(final_grade.value) if final_grade else 0)
			row.append( 100 )

			# End-of-line
			row.append('#')

			rows.append(row)

		# Anyone enrolled but not submitted gets a blank row
		# at the bottom...except that breaks the D2L model

		# Convert to CSV
		# In the future, we might switch based on the accept header
		# and provide it as json or XLS alternately
		buf = StringIO()
		writer = csv.writer(buf)
		writer.writerows(rows)

		self.request.response.body = buf.getvalue()
		self.request.response.content_disposition = b'attachment; filename="contents.csv"'

		return self.request.response
