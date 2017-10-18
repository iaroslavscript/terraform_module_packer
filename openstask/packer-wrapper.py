#!/usr/bin/env python

from __future__ import print_function

import json
import os
import re
import subprocess
import shlex
import sys
import tempfile
import threading


class WrapperError(Exception):
    def __init__(self, error_msg):
        super(WrapperError, self).__init__(error_msg)


def golang_bool(value):
    return value in ('1', 'true') 


def validate_vars(data):
    default_config = {
        'args':    '',
        'timeout': 600,
        'rebuild': True,
    }
    
    required_keys = [
        'template_file',
        'image_id',
        'image_name',
    ]
    restricted_keys = [
        'var_',
        'env_',
    ]
    key_map = {
        'timeout': int,
        'rebuild': golang_bool,
    }

    input_data = {}
    input_data.update(default_config)
    input_data.update(data)

    for key in required_keys:
        if key not in input_data:
            raise WrapperError("Key '{}' required at input quiery".format(key))

    for key in restricted_keys:
        if key in input_data:
            raise WrapperError("Key '{}' is restricted key name at input quiery".format(key))

    template_vars = {}
    env_vars = {}
    config = {}
 
    for k,v in input_data.items():
        if k in key_map:
            v = key_map[ k ]( v )

        if k.startswith('var_'):
            template_vars[ k[4:] ] = v
        elif k.startswith('env_'):
            env_vars[ k[4:] ] = v
        else:
            config[ k ] = v

    for key in config.keys():
        if key not in default_config.keys()+required_keys:
            raise WrapperError("Key '{}' is unknown key name at input quiery".format(key))

    # pass variable image_name to template
    template_vars['image_name'] = config['image_name']

    return config, template_vars, env_vars


def process_term(proc):
    print('Timeout occured. Send SIGTERM to process', file=sys.stderr)
    proc.terminate()


def process_kill(proc):
   
    if proc.poll() is None:
        print('Timeout occured. Send SIGKILL to process', file=sys.stderr)
        proc.kill()
    
    raise WrapperError('Subprocess was killed by timeout')


def prepare_build_vars(data):
    result = ''

    if data:
        result = '-var ' + ' -var '.join(( "'{}={}'".format(k,v) for k,v in data.items()))

    return result


def update_env(env_vars):
    for k,v in env_vars:
        os.environ[ k ] = v


def packer_build(log_fd, build_args, build_vars, env_vars, packer_file, timeout_sec):

    image_id = None
    cmd = 'packer build {} {} {}'.format(
        build_args,
        prepare_build_vars(build_vars),
        packer_file,
    )

    update_env(env_vars)

    proc = subprocess.Popen(
        shlex.split(cmd),
        cwd=os.path.dirname(packer_file),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    timer_term = threading.Timer(timeout_sec, process_term, [proc])
    timer_kill = threading.Timer(timeout_sec + 2, process_kill, [proc])
    
    try:
        timer_term.start()
        timer_kill.start()
        
        while True:
            output = proc.stdout.readline()
            if output == '' and proc.poll() is not None:
                break
            log_fd.write(output)            

            value = extract_image_id(output)
            if value:
                image_id = value
    finally:
        timer_term.cancel()
        timer_kill.cancel()

    if 0 != proc.returncode:
        raise WrapperError('{}\nPacker finished with non zero return code {}'.format(
            open(log_fd.name).read(),  # TODO
            proc.returncode,
        ))

    if image_id is None:
        raise WrapperError('Unable to extract image id from packer stdout')

    return image_id


def extract_image_id(line):

    result = None
    m = re.match('--> openstack: An image was created:\s+(.+)$', line)

    if m:
        result = m.group(1).strip()

    return result


def prepare_response(data):
    result = {}    
    for k,v in data.items():
        result[ k ] = str(v)

    return json.dumps(result)


def image_exists(image_id):
    return image_id != '0'


def main():

    try:
        request = json.load(sys.stdin)
        config, template_vars, env_vars = validate_vars(request)
        log_fd = tempfile.NamedTemporaryFile(mode='w', delete=False)        
       
        response = {
            'image_id': config['image_id'],
        }
        
        with tempfile.NamedTemporaryFile(mode='w', delete=False) as log_fd:
            response['log'] = log_fd.name

            if not image_exists(config['image_id']) or config['rebuild']:
                
                image_id = packer_build(
                    log_fd,
                    config['args'],
                    template_vars,
                    env_vars,
                    config['template_file'],
                    config['timeout']
                )

                response['image_id'] = image_id
            
    except WrapperError as e:
        print(str(e), file=sys.stderr)
        sys.exit(1)

    response_json = prepare_response(response)

    # send results to terraform
    print(response_json)
    

if __name__ == '__main__':
    main()
    
