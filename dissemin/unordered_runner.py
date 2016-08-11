from django.test.runner import DiscoverRunner

class UnorderedTestRunner(DiscoverRunner):
  """ A test runner to test without test sorting """

  reorder_by = []


