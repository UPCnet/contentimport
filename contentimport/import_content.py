from App.config import getConfiguration
from collective.exportimport.import_content import ImportContent
from plone import api
from collective.exportimport import _
from ZPublisher.HTTPRequest import FileUpload
from six.moves.urllib.parse import unquote
from six.moves.urllib.parse import urlparse
from zope.component import getUtility
from plone.dexterity.interfaces import IDexterityFTI
from zope.annotation.interfaces import IAnnotations

import logging
import json
import os
import transaction
import ijson

logger = logging.getLogger(__name__)


# map old to new views
VIEW_MAPPING = {
    "atct_album_view": "album_view",
    "prettyPhoto_album_view": "album_view",
    "folder_full_view": "full_view",
    "folder_listing": "listing_view",
    "folder_summary_view": "summary_view",
    "folder_tabular_view": "tabular_view",
}

PORTAL_TYPE_MAPPING = {
    "Topic": "Collection",
}

REVIEW_STATE_MAPPING = {}

VERSIONED_TYPES = [
    "Document",
    "News Item",
    "Event",
    "Link",
]

IMPORTED_TYPES = [
    "ContentPanels",
    "Collection",
    "Topic",
    "Document",
    "Folder",
    "Link",
    "File",
    "Image",
    "News Item",
    "Event",
    "EasyForm",
    "BannerContainer",
    "Banner",
    "genweb.upc.documentimage",
    "genweb.upc.subhome",
    "LIF",
    "LRF",
    "Logos_Container",
    "Logos_Footer",
    "packet",
]

ALLOWED_TYPES = [
    "Collection",
    "Document",
    "Folder",
    "Link",
    "File",
    "Image",
    "News Item",
    "Event",
    "EasyForm",
    "BannerContainer",
    "Banner",
    "genweb.upc.documentimage",
    "genweb.upc.subhome",
    "LIF",
    "LRF",
    "Logos_Container",
    "Logos_Footer",
    "packet",
]

CUSTOMVIEWFIELDS_MAPPING = {
    "warnings": None,
}

ANNOTATIONS_KEY = "exportimport.annotations"

class CustomImportContent(ImportContent):

    DROP_PATHS = []

    DROP_UIDS = []

    def __call__(
        self,
        jsonfile=None,
        return_json=False,
        limit=None,
        server_file=None,
        iterator=None
    ):
        request = self.request
        self.limit = limit
        self.commit = int(request["commit"]) if request.get("commit") else None
        self.import_to_current_folder = request.get("import_to_current_folder", False)

        self.handle_existing_content = int(request.get("handle_existing_content", 1))
        self.handle_existing_content_options = (
            ("0", _("Skip: Don't import at all")),
            ("1", _("Replace: Delete item and create new")),
            ("2", _("Update: Reuse and only overwrite imported data")),
            ("3", _("Ignore: Create with a new id")),
        )
        self.import_old_revisions = request.get("import_old_revisions", False)

        if not self.request.form.get("form.submitted", False):
            return self.template()

        # If we open a server file, we should close it at the end.
        close_file = False
        status = "success"
        msg = ""
        if server_file and jsonfile:
            # This is an error.  But when you upload 10 GB AND select a server file,
            # it is a pity when you would have to upload again.
            api.portal.show_message(
                _(u"json file was uploaded, so the selected server file was ignored."),
                request=self.request,
                type="warn",
            )
            server_file = None
            status = "error"
        if server_file and not jsonfile:
            if server_file in self.server_files:
                for path in self.import_paths:
                    full_path = os.path.join(path, server_file)
                    if os.path.exists(full_path):
                        logger.info("Using server file %s", full_path)
                        # Open the file in binary mode and use it as jsonfile.
                        jsonfile = open(full_path, "rb")
                        close_file = True
                        break
            else:
                msg = _("File '{}' not found on server.").format(server_file)
                api.portal.show_message(msg, request=self.request, type="warn")
                server_file = None
                status = "error"
        if jsonfile:
            self.portal = api.portal.get()
            try:
                if isinstance(jsonfile, str):
                    return_json = True
                    data = ijson.items(jsonfile, "item")
                elif isinstance(jsonfile, FileUpload) or hasattr(jsonfile, "read"):
                    data = ijson.items(jsonfile, "item")
                else:
                    raise RuntimeError("Data is neither text, file nor upload.")
            except Exception as e:
                logger.error(str(e))
                status = "error"
                msg = str(e)
                api.portal.show_message(
                    _(u"Exception during upload: {}").format(e),
                    request=self.request,
                )
            else:
                self.start()
                msg = self.do_import(data)
                api.portal.show_message(msg, self.request)

        if close_file:
            jsonfile.close()

        if not jsonfile and iterator:
            self.start()
            msg = self.do_import(iterator)
            api.portal.show_message(msg, self.request)

        self.finish()

        if return_json:
            msg = {"state": status, "msg": msg}
            return json.dumps(msg)
        return self.template()

    def create_container(self, item):
        """Create container for item.

        See remarks in get_parent_as_container for some corner cases.
        """
        folder = self.context
        parent_url = unquote(item["parent"]["@id"])
        parent_url_parsed = urlparse(parent_url)
        # Get the path part, split it, remove the always empty first element.
        parent_path = parent_url_parsed.path.split("/")[1:]
        if (
            len(parent_url_parsed.netloc.split(":")) > 1
            or parent_url_parsed.netloc == "nohost"
        ):
            # For example localhost:8080, or nohost when running tests.
            # First element will then be a Plone Site id.
            # Get rid of it.
            parent_path = parent_path[1:]

        # Handle folderish Documents provided by plone.volto
        fti = getUtility(IDexterityFTI, name="Document")
        parent_type = "Document" if fti.klass.endswith("FolderishDocument") else "Folder"
        # create original structure for imported content
        for element in parent_path:
            #Migration genweb
            try:
                if element not in folder:
                    folder = api.content.create(
                        container=folder,
                        type=parent_type,
                        id=element,
                        title=element,
                    )
                    logger.info(u"Created container %s to hold %s", folder.absolute_url(), item["@id"])
                else:
                    folder = folder[element]
            except:
                logger.error(u"NOT Created container %s to hold %s", folder.absolute_url(), item["@id"])

        return folder

    def global_obj_hook(self, obj, item):
        item = self.import_annotations(obj, item)
        return item

    def import_annotations(self, obj, item):
        annotations = IAnnotations(obj)
        for key in item.get(ANNOTATIONS_KEY, []):
            annotations[key] = item[ANNOTATIONS_KEY][key]
        return item

    def set_uuid(self, item, obj):
        uuid = item.get("UID")
        if '-' in uuid:
            uuid = uuid.split('-')[:-1][0]
        if not uuid:
            return obj.UID()
        if not self.update_existing and api.content.find(UID=uuid):
            # this should only happen if you run import multiple times
            # without updating existing content
            uuid = obj.UID()
            logger.info(
                "UID {} of {} already in use by {}. Using {}".format(
                    item["UID"],
                    item["@id"],
                    api.content.get(UID=item["UID"]).absolute_url(),
                    uuid,
                ),
            )
        else:
            setattr(obj, "_plone.uuid", uuid)
            obj.reindexObject(idxs=["UID"])
        return uuid

#No lo utilizo son ejemplos de Philip Bauer
#     def start(self):
#         self.items_without_parent = []
#         portal_types = api.portal.get_tool("portal_types")
#         for portal_type in VERSIONED_TYPES:
#             fti = portal_types.get(portal_type)
#             behaviors = list(fti.behaviors)
#             if 'plone.versioning' in behaviors:
#                 logger.info(f"Disable versioning for {portal_type}")
#                 behaviors.remove('plone.versioning')
#             fti.behaviors = behaviors

#     def finish(self):
#         # export content without parents
#         if self.items_without_parent:
#             data = json.dumps(self.items_without_parent, sort_keys=True, indent=4)
#             number = len(self.items_without_parent)
#             cfg = getConfiguration()
#             filename = 'content_without_parent.json'
#             filepath = os.path.join(cfg.clienthome, filename)
#             with open(filepath, 'w') as f:
#                 f.write(data)
#             msg = u"Saved {} items without parent to {}".format(number, filepath)
#             logger.info(msg)
#             api.portal.show_message(msg, self.request)

#     def commit_hook(self, added, index):
#         msg = u"Committing after {} created items...".format(len(added))
#         logger.info(msg)
#         transaction.get().note(msg)
#         transaction.commit()
#         if self.items_without_parent:
#             data = json.dumps(self.items_without_parent, sort_keys=True, indent=4)
#             number = len(self.items_without_parent)
#             cfg = getConfiguration()
#             filename = f'content_without_parent_{index}.json'
#             filepath = os.path.join(cfg.clienthome, filename)
#             with open(filepath, 'w') as f:
#                 f.write(data)
#             msg = u"Saved {} items without parent to {}".format(number, filepath)
#             logger.info(msg)

#     def global_dict_hook(self, item):

#         # Adapt this to your site
#         old_portal_id = self.portal.id
#         new_portal_id = self.portal.id

#         # This is only relevant for items in the site-root.
#         # Most items containers are usually looked up by the uuid of the old parent
#         item["@id"] = item["@id"].replace(f"/{old_portal_id}/", f"/{new_portal_id}/", 1)
#         item["parent"]["@id"] = item["parent"]["@id"].replace(f"/{old_portal_id}", f"/{new_portal_id}", 1)

#         # update constraints
#         if item.get("exportimport.constrains"):
#             types_fixed = []
#             for portal_type in item["exportimport.constrains"]["locally_allowed_types"]:
#                 if portal_type in PORTAL_TYPE_MAPPING:
#                     types_fixed.append(PORTAL_TYPE_MAPPING[portal_type])
#                 elif portal_type in ALLOWED_TYPES:
#                     types_fixed.append(portal_type)
#             item["exportimport.constrains"]["locally_allowed_types"] = list(set(types_fixed))

#             types_fixed = []
#             for portal_type in item["exportimport.constrains"]["immediately_addable_types"]:
#                 if portal_type in PORTAL_TYPE_MAPPING:
#                     types_fixed.append(PORTAL_TYPE_MAPPING[portal_type])
#                 elif portal_type in ALLOWED_TYPES:
#                     types_fixed.append(portal_type)
#             item["exportimport.constrains"]["immediately_addable_types"] = list(set(types_fixed))

#         # Layouts...
#         if item.get("layout") in VIEW_MAPPING:
#             new_view = VIEW_MAPPING[item["layout"]]
#             if new_view:
#                 item["layout"] = new_view
#             else:
#                 # drop unsupported views
#                 item.pop("layout")

#         # Workflows...
#         if item.get("review_state") in REVIEW_STATE_MAPPING:
#             item["review_state"] = REVIEW_STATE_MAPPING[item["review_state"]]

#         # Expires before effective
#         effective = item.get('effective', None)
#         expires = item.get('expires', None)
#         if effective and expires and expires <= effective:
#             item.pop('expires')

#         # drop empty creator
#         item["creators"] = [i for i in item.get("creators", []) if i]

#         return item

#     def create_container(self, item):
#         """Override create_container to never create parents"""
#         # Indead of creating a folder we save all items where this happens in a new json-file
#         self.items_without_parent.append(item)

#     def dict_hook_folder(self, item):
#         return item

#     def dict_hook_topic(self, item):
#         item["@type"] = "Collection"
#         if item["parent"]["@type"] == "Topic":
#             logger.info(f"Skipping Subtopic {item['@id']}.")
#             return

#         old_fields = item.get("customViewFields", [])
#         fixed_fields = []
#         for field in old_fields:
#             if field in CUSTOMVIEWFIELDS_MAPPING:
#                 if CUSTOMVIEWFIELDS_MAPPING.get(field):
#                     fixed_fields.append(CUSTOMVIEWFIELDS_MAPPING.get(field))
#             else:
#                 fixed_fields.append(field)
#         if fixed_fields:
#             item["customViewFields"] = fixed_fields

#         item["query"] = fix_collection_query(item.pop("query", []))
#         if not item["query"]:
#             logger.info(f"Create collection without query: {item['@id']}")

#         return item

#     def dict_hook_collection(self, item):
#         old_fields = item.get("customViewFields", [])
#         fixed_fields = []
#         for field in old_fields:
#             if field in CUSTOMVIEWFIELDS_MAPPING:
#                 if CUSTOMVIEWFIELDS_MAPPING.get(field):
#                     fixed_fields.append(CUSTOMVIEWFIELDS_MAPPING.get(field))
#             else:
#                 fixed_fields.append(field)
#         if fixed_fields:
#             item["customViewFields"] = fixed_fields

#         item["query"] = fix_collection_query(item.pop("query", []))

#         if not item["query"]:
#             logger.info(f"Drop collection without query: {item['@id']}")
#             return

#         return item

#     def dict_hook_event(self, item):
#         # drop empty strings as event_url
#         if item.get("event_url", None) == "":
#             item.pop("event_url")
#         return item


# def fix_collection_query(query):
#     fixed_query = []

#     indexes_to_fix = [
#         u'portal_type',
#         u'review_state',
#         u'Creator',
#         u'Subject'
#     ]
#     operator_mapping = {
#         # old -> new
#         u"plone.app.querystring.operation.selection.is":
#             u"plone.app.querystring.operation.selection.any",
#         u"plone.app.querystring.operation.string.is":
#             u"plone.app.querystring.operation.selection.any",
#     }

#     for crit in query:
#         if crit["i"] == "portal_type" and len(crit["v"]) > 30:
#             # Criterion is all types
#             continue

#         if crit["o"].endswith("relativePath") and crit["v"] == "..":
#             # relativePath no longer accepts ..
#             crit["v"] = "..::1"

#         if crit["i"] in indexes_to_fix:
#             for old_operator, new_operator in operator_mapping.items():
#                 if crit["o"] == old_operator:
#                     crit["o"] = new_operator

#         if crit["i"] == "portal_type":
#             # Some types may have changed their names
#             fixed_types = []
#             for portal_type in crit["v"]:
#                 fixed_type = PORTAL_TYPE_MAPPING.get(portal_type, portal_type)
#                 fixed_types.append(fixed_type)
#             crit["v"] = list(set(fixed_types))

#         if crit["i"] == "review_state":
#             # Review states may have changed their names
#             fixed_states = []
#             for review_state in crit["v"]:
#                 fixed_state = REVIEW_STATE_MAPPING.get(review_state, review_state)
#                 fixed_states.append(fixed_state)
#             crit["v"] = list(set(fixed_states))

#         if crit["o"] == "plone.app.querystring.operation.string.currentUser":
#             crit["v"] = ""

#         fixed_query.append(crit)

#     return fixed_query
