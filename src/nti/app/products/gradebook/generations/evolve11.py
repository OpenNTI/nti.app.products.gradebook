#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
generation 27.

.. $Id$
"""

from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

generation = 11

from zope import component
from zope import interface

from zope.component.hooks import site
from zope.component.hooks import setHooks

from zope.event import notify

from zope.intid.interfaces import IIntIds

from zope.lifecycleevent import ObjectModifiedEvent

from nti.app.assessment.interfaces import IUsersCourseAssignmentHistory

from nti.app.products.gradebook.grades import GradeContainer
from nti.app.products.gradebook.grades import PersistentMetaGrade

from nti.app.products.gradebook.interfaces import IGrade
from nti.app.products.gradebook.interfaces import IGradeContainer

from nti.app.products.gradebook.subscribers.grades import _get_entry_change_storage

from nti.app.products.gradebook.utils.gradebook import save_in_container
from nti.app.products.gradebook.utils.gradebook import set_grade_by_assignment_history_item

from nti.assessment.interfaces import IPlaceholderAssignmentSubmission

from nti.contenttypes.courses.interfaces import ICourseInstance

from nti.dataserver.interfaces import IDataserver
from nti.dataserver.interfaces import IOIDResolver

from nti.dataserver.metadata.index import get_metadata_catalog

from nti.dataserver.users import User

logger = __import__('logging').getLogger(__name__)


@interface.implementer(IDataserver)
class MockDataserver(object):

    root = None

    def get_by_oid(self, oid, ignore_creator=False):
        resolver = component.queryUtility(IOIDResolver)
        if resolver is None:
            logger.warn("Using dataserver without a proper ISiteManager.")
        else:
            return resolver.get_object_by_oid(oid, ignore_creator=ignore_creator)
        return None


def _get_change_object(entry, grade):
    # These should all exist at this point
    storage = _get_entry_change_storage(entry)
    change_container = storage[grade.Username]
    try:
        change_key = grade.HistoryItemNTIID
    except AttributeError:
        change_key = u'MetaGrade'
    return change_container[change_key]


def _copy_dates(target_object, source_object):
    target_object.LastModified = source_object.LastModified
    target_object.createdTime = source_object.createdTime


def store_meta_grade(grade_container, grade, entry):
    meta_grade = PersistentMetaGrade(value=grade.value)
    meta_grade.__parent__ = grade_container
    grade_container.MetaGrade = meta_grade
    meta_grade.__name__ = u'MetaGrade'
    assert meta_grade.__parent__ is grade_container
    notify(ObjectModifiedEvent(grade))
    _copy_dates(meta_grade, grade)
    change_object = _get_change_object(entry, grade)
    _copy_dates(change_object, grade)


def _cleanup_entry_change_storage(entry, seen_entries):
    """
    Cleanup our entry change storage. We're going to create new grades during
    this migration, and, once the events are fired, we're going to have new
    change events. We'll want a clean slate so that we know our change storage
    is in the correct state once grade events start firing.
    """
    if entry.ntiid in seen_entries:
        return
    seen_entries.add(entry.ntiid)
    change_storage = _get_entry_change_storage(entry)
    change_storage.clear()


def do_evolve(context, generation=generation):
    logger.info("Grade container evolution %s started", generation)

    setHooks()
    conn = context.connection
    ds_folder = conn.root()['nti.dataserver']
    lsm = ds_folder.getSiteManager()

    mock_ds = MockDataserver()
    mock_ds.root = ds_folder
    component.provideUtility(mock_ds, IDataserver)
    intids = lsm.getUtility(IIntIds)

    with site(ds_folder):
        assert component.getSiteManager() == ds_folder.getSiteManager(), \
               "Hooks not installed?"

        total = 0
        meta_grade_count = 0
        grades_assessed = 0
        metadata_catalog = get_metadata_catalog()
        index = metadata_catalog['mimeType']

        seen_entries = set()
        MIME_TYPES = ('application/vnd.nextthought.grade',)
        item_intids = index.apply({'any_of': MIME_TYPES})
        for doc_id in item_intids or ():
            item = intids.queryObject(doc_id)
            if IGrade.providedBy(item):
                grade = item
                user = User.get_user(grade.__name__)
                course = ICourseInstance(grade, None)
                gradebook_entry = grade.__parent__
                if user is None:
                    logger.warn('Grade without user (%s)', grade)
                    continue

                if gradebook_entry is None:
                    logger.warn('Grade without lineage (%s)', grade)
                    continue

                if course is None:
                    logger.warn('Grade without course (%s)', grade)
                    continue

                if IGradeContainer.providedBy(gradebook_entry):
                    # Idempotent
                    continue

                _cleanup_entry_change_storage(gradebook_entry, seen_entries)
                grade_container = GradeContainer()
                # Remove grade (no event)
                gradebook_entry._delitemf(grade.__name__, event=False)
                # Store our new, empty container
                save_in_container(gradebook_entry, user.username, grade_container)

                total += 1
                if total % 100 == 0:
                    logger.info('%s grade containers added', total)

                # We may have multiple submissions at this point.
                # If we have a single submission:
                # * if placeholder, we have a MetaGrade
                # * otherwise, we have a grade for the history_item
                #
                # If we have multiple submissions, we need to re-assess and re-grade
                # * if our grade does not match assessed grade, we have a meta grade
                # * store each assessed grade as a new grade for the history item
                assignment_ntiid = grade.AssignmentId
                container = component.queryMultiAdapter((course, user),
                                                        IUsersCourseAssignmentHistory)
                submission_container = None
                if container is not None:
                    submission_container = container.get(assignment_ntiid)
                if submission_container is None:
                    # This should not be possible
                    meta_grade_count += 1
                    store_meta_grade(grade_container, grade, gradebook_entry)
                else:
                    new_grades = []
                    for history_item in submission_container.values():
                        if IPlaceholderAssignmentSubmission.providedBy(history_item.Submission):
                            continue
                        # This will grade and store in our (new) grade_container, if possible
                        # These grades should be tied to the history item.
                        # This should do whatever events we need
                        # XXX: This will emit non-harmful warning messages about auto-grading
                        # non-auto-grading types. This is expected.

                        # We should have no events here
                        # This should always be a new grade
                        new_grade = set_grade_by_assignment_history_item(history_item,
                                                                         overwrite=True)
                        notify(ObjectModifiedEvent(new_grade))
                        _copy_dates(new_grade, grade)
                        change_object = _get_change_object(gradebook_entry, grade)
                        _copy_dates(change_object, grade)
                        grades_assessed += 1
                        new_grades.append(new_grade)

                    grade_values = [x.value for x in new_grades]
                    if grade.value not in grade_values:
                        # We have a MetaGrade; this is also the case if we just have a
                        # placeholder submission
                        meta_grade_count += 1
                        store_meta_grade(grade_container, grade, gradebook_entry)

    component.getGlobalSiteManager().unregisterUtility(mock_ds, IDataserver)
    logger.info('Grade container evolution %s done (grade_containers=%s) (meta_grades=%s) (history_items_assessed=%s)',
                generation, total, meta_grade_count, grades_assessed)


def evolve(context):
    """
    Evolve to generation 11 to put all grades into the new GradeContainer.

    XXX: Do we need to migrate change storage
    XXX: Do we need to remove placeholder submissions
    """
    do_evolve(context)
