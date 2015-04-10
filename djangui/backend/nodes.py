__author__ = 'chris'
import argparse
import sys
import copy
import os
from . import utils

def filetype_filefield_default(kwargs, attr, default_kwargs, action, extra=None):
    model_name = default_kwargs['model_name']
    value = getattr(action, attr)
    # import pdb; pdb.set_trace();
    if value in (None, sys.stderr, sys.stdout, os.devnull):
        # For files we are saving (out script output), handle cases where they are
        # going to stdout/etc.
        if not is_upload(action) and not action.required:
            kwargs['blank'] = True
            if value == sys.stderr:
                kwargs['default'] = "'stderr'"
            elif value == sys.stdout:
                kwargs['default'] = "'stdout'"
            elif value == os.devnull:
                kwargs['default'] = "'null'"
        model_name = 'upload_to'
        value = ['user_upload' if is_upload(action) else 'user_output']
        value.append("" if extra is None else extra.get('class_name', ''))
        value = "'{0}'".format(os.path.join(*value))
    kwargs[model_name] = value

def str_charfield_default(kwargs, attr, default_kwargs, action, extra=None):
    model_name = default_kwargs['model_name']
    value = getattr(action, attr)
    kwargs[model_name] = '"{0}"'.format(value)

UNIVERSAL_KWARGS = {
    'required': {'model_name': 'blank'},
    'default': {'model_name': 'default'}
    }

TYPE_FIELDS = {
    int: {'field': 'CharField', 'kwargs': {'max_length': 255}},
    str: {'field': 'CharField', 'kwargs': {'max_length': 255},
          'getattr_kwargs': {'default': {'model_name': 'default', 'callback': str_charfield_default}}},
    bool: {'field': 'BooleanField',},
    argparse.FileType: {'field': 'FileField',
                        'getattr_kwargs': {'default': {'model_name': 'default', 'callback': filetype_filefield_default}}}
}

ACTION_CLASS_TO_MODEL_FIELD = {
    argparse._StoreAction: dict(TYPE_FIELDS, **{

    }),
    argparse._StoreConstAction: dict(TYPE_FIELDS, **{

    }),
    argparse._StoreTrueAction: dict(TYPE_FIELDS, **{
        None: {'field': 'BooleanField', 'kwargs': {'blank': True},},
    }),
    argparse._StoreFalseAction: dict(TYPE_FIELDS, **{
        None: {'field': 'BooleanField', 'kwargs': {'blank': True},},
    })
}

def is_upload(action):
    """Checks if this should be a user upload

    :param action:
    :return: True if this is a file we intend to upload from the user
    """
    # import pdb; pdb.set_trace();
    return 'r' in action.type._mode and (action.default is None or
                                         getattr(action.default, 'name') not in (sys.stderr.name, sys.stdout.name))

class ArgParseNode(object):
    """
        This class takes an argument parser entry and assigns it to a Django field
    """
    def __init__(self, action=None, model_field=None, class_name=''):
        try:
            model_field = copy.deepcopy(model_field)
            field = model_field['field']
            self.field_module = 'models'
            if field == 'FileField':
                self.field_module = 'djangui_fields'
                if is_upload(action):
                    field = 'DjanguiUploadFileField'
                else:
                    field = 'DjanguiOutputFileField'
            #         # it's somewhere we're saving output to
            #         model_field = copy.deepcopy(TYPE_FIELDS[str])
            #         field = model_field['field']
            #         del model_field['getattr_kwargs']
            self.kwargs = model_field.get('kwargs', {})
            self.kwargs.update({'help_text': '"{0}"'.format(utils.sanitize_string(action.help))})
            getattr_kwargs = copy.deepcopy(UNIVERSAL_KWARGS)
            getattr_kwargs.update(model_field.get('getattr_kwargs', {}))
            for attr, attr_dict in getattr_kwargs.iteritems():
                cb = attr_dict.get('callback', None)
                if cb is not None:
                    cb(self.kwargs, attr, attr_dict, action, extra={'class_name': class_name})
                else:
                    model_name = attr_dict['model_name']
                    value = getattr(action, attr)
                    self.kwargs[model_name] = value
            self.name = action.dest
            self.field = field
        except:
            import traceback
            print traceback.format_exc()
            import pdb; pdb.set_trace();

    def __unicode__(self):
        return u'{0} = {3}.{1}({2})'.format(self.name, self.field,
                                               ', '.join(['{0}={1}'.format(i,v) for i,v in self.kwargs.iteritems()]),
                                               self.field_module)

    def __str__(self):
        return str(self.__unicode__())

class ArgParseNodeBuilder(object):
    def __init__(self, script, parser, script_path):

        self.nodes = []
        self.djangui_options = {}
        # places to save files to
        self.djangui_output_defaults = {}
        self.class_name = script
        self.script_path = script_path
        for action in parser._actions:
            # This is the help message of argparse
            if action.default == argparse.SUPPRESS:
                continue
            fields = ACTION_CLASS_TO_MODEL_FIELD.get(type(action), TYPE_FIELDS)
            field_type = fields.get(action.type)
            # print action
            if field_type is None:
                field_types = [i for i in fields.keys() if issubclass(type(action.type), i)]
                if len(field_types) > 1:
                    field_types = [i for i in fields.keys() if isinstance(action.type, i)]
                if len(field_types) == 1:
                    field_type = fields[field_types[0]]
                else:
                    print 'NOOO'
                    continue
            node = ArgParseNode(action=action, model_field=field_type, class_name=self.class_name)
            self.nodes.append(node)
            self.djangui_options[action.dest] = action.option_strings[0]
            if node.field == 'DjanguiOutputFileField':
                self.djangui_output_defaults[action.dest] = node.kwargs.get('default')

    def getModelDict(self):
        fields = [u'djangui_script_name = models.CharField(max_length=255, default="{0}")'.format(self.script_path)]
        fields += [str(node) for node in self.nodes]
        return {'class_name': self.class_name, 'fields': fields, 'djangui_options': self.djangui_options,
                'djangui_output_defaults': self.djangui_output_defaults}