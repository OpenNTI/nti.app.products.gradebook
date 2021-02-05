from __future__ import division
from __future__ import print_function
from __future__ import absolute_import

from zope import component
from zope import interface

from nti.app.products.gradebook.interfaces import IGrade

from nti.app.pushnotifications.interfaces import INotableDataEmailClassifier

from nti.externalization.singleton import Singleton


@component.adapter(IGrade)
@interface.implementer(INotableDataEmailClassifier)
class _GradeNotableClassifier(Singleton):

    classification = 'grade'

    def classify(self, unused_obj):
        return self.classification
