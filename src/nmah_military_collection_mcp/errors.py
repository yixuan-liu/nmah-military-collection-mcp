class CollectionError(Exception):
    """A safe error that can be reported to a tool caller."""


class SmithsonianAPIError(CollectionError):
    """Open Access configuration, request, or response failure."""


class RecordScopeError(CollectionError):
    """The requested record could not be verified within the collection."""


class ImageManifestError(CollectionError):
    """A public image manifest could not be checked."""
