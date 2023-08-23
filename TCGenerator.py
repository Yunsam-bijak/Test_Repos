import os
import sys
import base64
import shutil
import hashlib
import re
import glob
from collections import defaultdict
import subprocess
import asyncio
import time
from crown_tc_viewer_maker import TCResultMaker
from AddTC import AddTC
from itertools import chain
import json
from Logger import logger

class TCGenerator:
    func_list = []
    file_path = ''
    state = ''
    func_id = ''
    strategy = ''
    execution_timeout = 0
    function_timeout = 0
    max_test = 0
    use_sanitizer = False
    status = ''
    timeout_reached = False
    crash_list = []

    def __init__ (self, func_list):
        self.func_list = func_list
        self.state = 'Init'

    def clear (self):
        self.file_path = ''
        self.state = ''
        self.strategy = ''
        self.execution_timeout = 0
        self.function_timeout = 0
        self.max_test = 0
        self.use_sanitizer = False
        self.status = ''
        self.timeout_reached = False
        self.crash_list = []

    def convert_base64_to_divided_data(self, base64_data):
        data_bytes = base64.b64decode(base64_data)
        data = data_bytes.decode('ascii')
        func_start = data.rfind('/')
        func_name = data[func_start+1:]
        file_start = data.rfind('/',0,func_start-1)
        file_name = data[file_start+1:func_start] + '.i'
        location = data[:file_start]
        sys.stderr.write('Converted Result. File_location: {} file_name: {} func_name: {}\n'.format(location,file_name,func_name))
        return location, file_name, func_name

    def generate_json_data(self, output_path, file_name, func_name, crash_list, array_size, max_array_size =10):
        sym_var_filename = output_path + os.sep + file_name + '.' + func_name + '.sym_var.txt'
        target_tc_dir = output_path + os.sep + file_name + '.' + func_name + '.unique'
        tc_result =TCResultMaker()
        var_list = tc_result.get_sym_var_list(sym_var_filename)
        #sys.stderr.write('var list: ' + str(var_list)+ '\n')
        cur_dir = os.getcwd()
        os.chdir(output_path)
        header = tc_result.make_header(file_name , func_name, crash_list)
        os.chdir(target_tc_dir)
        json_file = output_path + os.sep + file_name + '.' + func_name + '.output.json'
        with open (json_file,'w') as f:
            json.dump(header, f, indent=4)
        #tc_result.make_result_json(var_list, target_tc_dir, crash_list, header, file_name, func_name)
        os.chdir(cur_dir)
        return True

    def delete_test_data(self, output_path, file_name, func_name):
        logger.info('[TCGenerator] Delete Previous Test Result of [{}] [{}] [{}]'.format(output_path, file_name, func_name))
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver_replay'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver_replay')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver.cil.c'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver.cil.c')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver.cil.i'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver.cil.i')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver.gcno'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver.gcno')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver.gcda'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver.gcda')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver.i'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver.i')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver.o'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver.o')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.output.json'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.output.json')
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.driver_fuzz'):
        #    os.remove(output_path + os.sep + file_name + '.' + func_name + '.driver_fuzz')

        for strategy in ['dfs','rev-dfs','random','random_input','cfg','seed','AFL']:
            if os.path.isdir(output_path + os.sep + file_name + '.' + func_name + '.' + strategy):
                shutil.rmtree(output_path + os.sep + file_name + '.' + func_name + '.' + strategy, ignore_errors=True)
        if os.path.exists(output_path + os.sep + file_name + '.' + func_name):
            shutil.rmtree(output_path + os.sep + file_name + '.' + func_name, ignore_errors=True)

        #commnet out becase of TC accumlatation
        #if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.unique'):
        #    shutil.rmtree(output_path + os.sep + file_name + '.' + func_name + '.unique', ignore_errors=True)

        if os.path.exists(output_path + os.sep + file_name + '.' + func_name + '.crash'):
            shutil.rmtree(output_path + os.sep + file_name + '.' + func_name + '.crash', ignore_errors=True)
   
        if os.path.exists(output_path + os.sep + 'crash_info'):
            for crash_file in os.listdir(output_path + os.sep + 'crash_info'):
                if crash_file.startswith(file_name + '.' + func_name):
                    os.remove(output_path + os.sep + 'crash_info' + os.sep + crash_file)

    def get_current_state(self, tc_gen_queue):
        total_tc = 0
        unique_tc = 0
        crash_tc = 0
        strategy = ''
        #sys.stderr.write('fil_path: {} state: {}\n'.format(self.file_path, self.state))
        if self.file_path == '' or self.state == '':
            return False
        if self.state.startswith('crown_tc_gen:'):
            logger.info('[TCGenerator] Get TC Gen State of {}'.format(self.file_path))
            if self.state.find('dfs') != -1:
                if unique_tc ==0 or crash_tc == 0:
                    unique_tc = 0
                    crash_tc = 0
                    total_tc = 0
                result_dir = self.file_path + '.' + strategy
                if not os.path.isdir(result_dir):
                    tc_gen_queue.put_nowait((self.func_id, 0, 0, 0, False,'Tc gen directory not found', self.strategy, self.execution_timeout, self.function_timeout, self.max_test, self.use_sanitizer))
                    return False
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                total_tc = len(tcs)
                 #return (total_tc,0,0, 'Tc gen processing')
                tc_gen_queue.put_nowait((self.func_id, total_tc, 0, 0, 'Tc gen processing', self.strategy, self.execution_timeout, self.function_timeout, self.max_test, self.use_sanitizer))
        elif self.state == 'duplicate_remove':
            logger.info('[TCGenerator] Duplicate Removing of {}'.format(self.file_path))
            if strategy != '':
                result_dir = self.file_path + '.' + strategy
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                total_tc = len(tcs)
                strategy = ''
            result_dir = self.file_path + '.unique'
            if not os.path.isdir(result_dir):
                tc_gen_queue.put_nowait((total_tc, 0, 0, 'Unique directory not found'))
                return False
            tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
            unique_tc = len(tcs)
            #return (total_tc,unique_tc,0, 'Duplicate removing')
            tc_gen_queue.put_nowait((total_tc, unique_tc, 0, 'Duplicate Removing'))
        elif self.state == 'run_replay':
            logger.info('[TCGenerator] Replay Running of {}'.format(self.file_path))
            if unique_tc == 0:
                result_dir = self.file_path + '.' + strategy
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                total_tc = len(tcs)
                result_dir = self.file_path + '.unique'
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                unique_tc = len(tcs)
            result_dir = self.file_path + '.crash'
            if not os.path.isdir(result_dir):
                tc_gen_queue.put_nowait((total_tc, unique_tc, 0, 'Running replay'))
                return False
            tcs = sorted([x for x in os.listdir(result_dir) if x.find('.input_trace.') != -1], reverse=True)
            crash_tc = len(tcs)
            tc_gen_queue.put_nowait((total_tc, unique_tc, crash_tc, 'Running replay'))
        return True

    def get_result(self):
        total_tc = 0
        unique_tc = 0
        crash_tc = 0
        sys.stderr.write('file path: {}\n'.format(self.file_path))
        if self.crownc_error_check(self.file_path+'.driver') < 0:
            logger.info('[TCGenerator] Compile Error [{}]'.format(self.file_path))
            return -1, -1, -1
        result_dir = self.file_path + '.' + self.strategy
        if os.path.isdir(result_dir):
            tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
            total_tc = len(tcs)
        result_dir = self.file_path + '.unique'
        if os.path.isdir(result_dir):
            tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
            unique_tc = len(tcs)
        result_dir = self.file_path + '.crash'
        if os.path.isdir(result_dir):
            tcs = sorted([x for x in os.listdir(result_dir) if x.endswith('.txt')], reverse=True)
            crash_tc = len(tcs)
        logger.info('[TCGenerator] Result of {}. # of Total TC: [{}], Unique TC: [{}], Crash TC: [{}]'.format(total_tc, unique_tc, crash_tc))
        return total_tc, unique_tc, crash_tc

    def get_current_state2(self, tc_gen_queue, recv_conn):
        total_tc = -1
        unique_tc = -1
        crash_tc = -1
        strategy = ''
        while self.state != '':
            time.sleep(1)
            if recv_conn.poll():
                if self.file_path == '':
                    self.file_path = recv_conn.recv()
                else:
                    self.state = recv_conn.recv()
                    if self.state.startswith('crown_tc_gen:'):
                        self.strategy = self.state.replace('crown_tc_gen:','')
            sys.stderr.write('fil_path: {} state: {}\n'.format(self.file_path, self.state))
            if self.file_path == '' or self.state == '':
                continue
            
            if self.state.startswith('crown_tc_gen:'):
                sys.stderr.write('current state: {}\n'.format(self.state))
                if self.state.find('rev-dfs') != -1:
                    strategy = self.state[13:]
                    #strategy = 'rev-dfs'
                    if unique_tc ==0 or crash_tc == 0:
                        unique_tc = 0
                        crash_tc = 0
                        total_tc = 0
                    result_dir = self.file_path + '.' + strategy
                    sys.stderr.write('result dir: {}\n'.format(result_dir))
                    if not os.path.isdir(result_dir):
                        tc_gen_queue.put_nowait((0, 0, 0, self.timeout_reached, 'Tc gen directory not found'))
                        continue
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                    total_tc = len(tcs)
                    sys.stderr.write('total tc: {}\n'.format(total_tc))
                    #return (total_tc,0,0, 'Tc gen processing')
                    tc_gen_queue.put_nowait((total_tc, 0, 0, self.timeout_reached, 'Tc gen processing'))
                elif self.state.find('dfs') != -1:
                    strategy = self.state[13:]
                    #strategy = 'dfs'
                    if unique_tc ==0 or crash_tc == 0:
                        unique_tc = 0
                        crash_tc = 0
                        total_tc = 0
                    result_dir = self.file_path + '.' + strategy
                    sys.stderr.write('result dir: {}\n'.format(result_dir))
                    if not os.path.isdir(result_dir):
                        tc_gen_queue.put_nowait((0, 0, 0, self.timeout_reached, 'Tc gen directory not found'))
                        #break
                        continue
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True) 
                    total_tc = len(tcs)
                    sys.stderr.write('total tc: {}\n'.format(total_tc))
                    #return (total_tc,0,0, 'Tc gen processing')
                    tc_gen_queue.put_nowait((total_tc, 0, 0, self.timeout_reached, 'Tc gen processing'))
                elif self.state.find('cfg') != -1:
                    #strategy = 'cfg'
                    strategy = self.state[13:]
                    if unique_tc ==0 or crash_tc == 0:
                        unique_tc = 0
                        crash_tc = 0
                        total_tc = 0
                    result_dir = self.file_path + '.' + strategy
                    sys.stderr.write('result dir: {}\n'.format(result_dir))
                    if not os.path.isdir(result_dir):
                        tc_gen_queue.put_nowait((0, 0, 0, self.timeout_reached, 'Tc gen directory not found'))
                        #break
                        continue
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                    total_tc = len(tcs)
                    sys.stderr.write('total tc: {}\n'.format(total_tc))
                    #return (total_tc,0,0, 'Tc gen processing')
                    tc_gen_queue.put_nowait((total_tc, 0, 0, self.timeout_reached, 'Tc gen processing'))
                elif self.state.find('random') != -1:
                    strategy = self.state[13:]
                    if unique_tc ==0 or crash_tc == 0:
                        unique_tc = 0
                        crash_tc = 0
                        total_tc = 0
                    result_dir = self.file_path + '.' + strategy
                    sys.stderr.write('result dir: {}\n'.format(result_dir))
                    if not os.path.isdir(result_dir):
                        tc_gen_queue.put_nowait((0, 0, 0, self.timeout_reached, 'Tc gen directory not found'))
                        continue
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                    total_tc = len(tcs)
                    sys.stderr.write('total tc: {}\n'.format(total_tc))
                    #return (total_tc,0,0, 'Tc gen processing')
                    tc_gen_queue.put_nowait((total_tc, 0, 0, self.timeout_reached, 'Tc gen processing'))
                elif self.state.find('combinedSS') != -1:
                    strategy = 'combinedSS'
                    #strategy = 'dfs'
                    if unique_tc ==0 or crash_tc == 0:
                        unique_tc = 0
                        crash_tc = 0
                    total_tc = 0  
                    result_dir = self.file_path + '.dfs'
                    if os.path.isdir(result_dir):  
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)      
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    tc_gen_queue.put_nowait((total_tc, 0, 0, self.timeout_reached, 'Tc gen processing'))
                elif self.state.find('AFL') != -1:
                    strategy='AFL'
                    result_dir = self.file_path + '.' + strategy
                    sys.stderr.write('result dir: {}\n'.format(result_dir))
                    if not os.path.isdir(result_dir):
                        tc_gen_queue.put_nowait((0, 0, 0, self.timeout_reached, 'Tc gen directory not found'))
                        continue
                    tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                    total_tc = len(tcs)
                    sys.stderr.write('total tc: {}\n'.format(total_tc))
                    #return (total_tc,0,0, 'Tc gen processing')
                    tc_gen_queue.put_nowait((total_tc, 0, 0, self.timeout_reached, 'Tc gen processing'))
                elif self.state.find('AFL Combined'):
                    if unique_tc ==0 or crash_tc == 0:
                        unique_tc = 0
                        crash_tc = 0
                    total_tc = 0
                    result_dir = self.file_path + '.dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.AFL'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    
                    tc_gen_queue.put_nowait((total_tc, 0, 0, self.timeout_reached, 'Tc gen processing'))
            elif self.state.startswith('duplicate_remove'):
                if self.state.find('with timeout') != -1:
                    self.timeout_reached = True
                else:
                    self.timeout_reached = False
                if strategy != '' and strategy != 'AFL' and strategy != 'combinedSS' and strategy != 'AFL Combined':
                    result_dir = self.file_path + '.' + strategy
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                    total_tc = len(tcs)
                    #strategy = ''
                elif strategy == 'combinedSS':
                    total_tc = 0
                    result_dir = self.file_path + '.dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                elif strategy == 'AFL Combined':
                    result_dir = self.file_path + '.dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.AFL'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                        total_tc = total_tc + len(tcs)
                
                elif strategy == 'AFL':
                    result_dir = self.file_path + '.AFL'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                        total_tc = len(tcs)

                result_dir = self.file_path + '.unique'
                if not os.path.isdir(result_dir):
                    tc_gen_queue.put_nowait((total_tc,  0, 0, self.timeout_reached, 'Unique directory not found'))
                    continue
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                unique_tc = len(tcs)
                #result_dir = result_dir = self.file_path + '.' + self.strategy
                #tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                #total_tc = len(tcs)
                #return (total_tc,unique_tc,0, 'Duplicate removing')
                tc_gen_queue.put_nowait((total_tc, unique_tc, 0, self.timeout_reached, 'Duplicate Removing'))

            elif self.state == 'run_replay':
                sys.stderr.write('strategy: {}\n'.format(strategy))
                #if unique_tc == 0 or unique_tc == -1:
                result_dir = self.file_path + '.' + strategy
                total_tc = 0
                if strategy == 'AFL':
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                        total_tc = len(tcs)
                elif strategy == 'combinedSS':
                    total_tc = 0
                    result_dir = self.file_path + '.dfs'

                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                        result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                else:
                #result_dir = self.file_path + '.' + strategy
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                    total_tc = len(tcs)
                result_dir = self.file_path + '.unique'
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                unique_tc = len(tcs)
                result_dir = self.file_path + '.crash'
                if not os.path.isdir(result_dir):
                    tc_gen_queue.put_nowait((total_tc, unique_tc, 0, self.timeout_reached, 'Running replay'))
                    continue
                tcs = sorted([x for x in os.listdir(result_dir) if x.find('.input_trace.') != -1], reverse=True)
                crash_tc = len(tcs)
                result_dir = self.file_path + '.unique'
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                unique_tc = len(tcs)
                if strategy != '' and strategy != 'AFL' and strategy != 'combinedSS':
                    result_dir = self.file_path + '.' + strategy
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                    total_tc = len(tcs)
                    #strategy = ''
                elif strategy == 'combinedSS':
                    total_tc = 0
                    result_dir = self.file_path + '.dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                        result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                elif strategy == 'AFL Combined':
                    result_dir = self.file_path + '.dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.AFL'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                        total_tc = total_tc + len(tcs)
                elif strategy == 'AFL':
                    result_dir = self.file_path + '.AFL'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                        total_tc = len(tcs)

                #result_dir = result_dir = self.file_path + '.' + self.strategy
                #tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                #total_tc = len(tcs)
                tc_gen_queue.put_nowait((total_tc, unique_tc, crash_tc, self.timeout_reached, 'Running replay'))
            elif self.state == 'success':
                result_dir = self.file_path + '.' + strategy
                tcs = []
                total_tc = 0
                if strategy == 'AFL':
                    tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                elif strategy == 'combinedSS':
                    total_tc = 0
                    result_dir = self.file_path + '.dfs'

                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                else:
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                    total_tc = len(tcs)
                result_dir = self.file_path + '.unique'
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                unique_tc = len(tcs)
                result_dir = self.file_path + '.crash'
                if not os.path.isdir(result_dir):
                    tc_gen_queue.put_nowait((total_tc, unique_tc, 0, self.timeout_reached, 'Success'))
                    break
                tcs = sorted([x for x in os.listdir(result_dir) if x.find('.input_trace.') != -1], reverse=True)
                crash_tc = len(tcs)
                result_dir = self.file_path + '.unique'
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                unique_tc = len(tcs)
                if strategy != '' and strategy != 'AFL' and strategy != 'combinedSS':
                    result_dir = self.file_path + '.' + strategy
                    tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                    total_tc = len(tcs)
                    strategy = ''
                elif strategy == 'combinedSS':
                    total_tc = 0
                    result_dir = self.file_path + '.dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                elif strategy == 'AFL Combined':
                    result_dir = self.file_path + '.dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = len(tcs)
                    result_dir = self.file_path + '.rev-dfs'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.cfg'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.random'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                        total_tc = total_tc + len(tcs)
                    result_dir = self.file_path + '.AFL'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                        total_tc = total_tc + len(tcs)
                elif strategy == 'AFL':
                    result_dir = self.file_path + '.AFL'
                    if os.path.isdir(result_dir):
                        tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
                        total_tc = len(tcs)
                #result_dir = result_dir = self.file_path + '.' + self.strategy
                #tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                #total_tc = len(tcs)
                tc_gen_queue.put_nowait((total_tc, unique_tc, crash_tc, self.timeout_reached, 'Success'))
                return
            elif self.state == 'user stop':
                tc_gen_queue.put_nowait((-2, -2, -2, False , 'User Stopped'))
                self.strategy = ''
                return
            elif self.state == 'Driver Compile Failed':
                tc_gen_queue.put_nowait((-1, -1, -1, False , 'Driver Compile Failed'))
                return
            elif self.state == 'Stop':
                return
            else:
                tc_gen_queue.put_nowait((0, 0, 0, False, 'Init'))
        #self.strategy = ''

    def run_as_web_server_tc_gen(self, tc_generator_path, working_dir, workspace_name, project_name, tc_gen_queue):
        sys.stderr.write('working_dir: {}\n'.format(working_dir))
        target_directory = working_dir + workspace_name + os.sep + project_name + os.sep + 'output'
        
        for func in self.func_list:
            file_location, file_name, func_name = self.convert_base64_to_divided_data(func['id'])
            file_path = target_directory + os.sep + file_location + os.sep + file_name
            sys.stderr.write('file path: ' + file_path + '\n')
            if os.path.isfile(file_path):
                sys.stderr.write('Run tc gen with file {} and function {} \n'.format(file_path, func_name))
                self.run_single_function_tc_generator(tc_generator_path, target_directory, file_location, file_name, func_name, func['options']['strategy'], func['options']['executionTimeout'], func['options']['functionTimeout'], func['options']['maxTest'], func['options']['useSanitizer'], func['id'], tc_gen_queue)
            else:
                sys.stderr.write('Fail to gen tcs\n')
                tc_gen_queue.put_nowait((func['id'], {'uniqueTC': 0, 'allTC':0, 'crashTC': 0, 'functionTimeout': None, 'status':'TC_gen_failed'}))

    def add_simple_tc(self, crash_gen_path,target_directory, location, file_name, func_name, tc_file, array_size, crash_list):
        cur_dir = os.getcwd()
        os.chdir(target_directory + os.sep + location)
        sys.stderr.write('test directory: {}\n'.format(os.getcwd()))
        user_tc_dir = file_name[:-2] + '.' + func_name + '.user_tc'
        unique_tc_dir = file_name[:-2] + '.' + func_name + '.unique'
        tc_num = AddTC.addSimpleTC(tc_file, file_name[:-2] + '.' + func_name)
        replay_target = './' + file_name[:len(file_name)-2] + '.' + func_name + '.driver_replay'
        replay_cmd = 'timeout -s SIGTERM -k 10 --preserve-status 5 ' + replay_target +' >> log/{}.{}.replay.log 2>&1'.format(file_name[:-4],func_name)
        if os.path.isfile('.CROWN.input_trace.txt'):
            print('Removing: .CROWN.input_trace.txt')
            os.remove('.CROWN.input_trace.txt')
        fileList = glob.glob('.CROWN.input_trace.*.txt')

        #for file in fileList:
        #    try:
        #        os.remove(file)
        #    except:
        #        print("Fail to remove : "+file)

        crash_num = len(fileList) +1
        replay_dir_prefix = file_name[:-2] + '.' + func_name
        replay_dir = file_name[:len(file_name)-2] + '.' + func_name + '.unique'
        crash_dir = replay_dir_prefix + '.crash'
        source_file = file_name
        crash_prefix = crash_dir + os.sep + file_name[:len(file_name)-2] + '.' + func_name + '.crashtc'
        crash_input_prefix = crash_dir + os.sep + file_name[:len(file_name)-2] + '.' + func_name + '.input_trace.'
        original_file = os.getcwd().replace('/output/','/src/') + os.sep + file_name[:-2]
        crash_array_size = array_size

        os.environ["CROWN_TC_FILE"] = replay_dir+'/input.'+str(tc_num)
        print('CROWN_TC_FILE: ' + os.environ["CROWN_TC_FILE"])
        shutil.copy(replay_dir+'/input.'+str(tc_num), 'input')
        ret = subprocess.run(replay_cmd, shell=True)
        print("Iteration " + str(tc_num) + "  Return value: " + str(ret) )
        print("----------------------")
        #if os.path.isfile('.CROWN.input_trace.txt') == True and ret.returncode != 0:
        if os.path.isfile('.CROWN.input_trace.txt'):
            sys.stderr.write('Crash with input.'+str(tc_num))
            sys.stderr.write('Crash dir: {}\n'.format(crash_dir))
            if os.path.exists(crash_dir) == False:
                os.mkdir(crash_dir)
            sys.stderr.write('Source File: {}\n'.format(source_file))
            if os.path.exists(source_file) and not os.path.exists(crash_dir + os.sep + source_file) :
                shutil.copy(source_file, crash_dir)
            sys.stderr.write('Original File: {}\n'.format(original_file))
            if os.path.exists(original_file) and not os.path.exists(crash_dir + os.sep + original_file) :
                shutil.copy(original_file, crash_dir)
            os.rename('.CROWN.input_trace.txt', crash_dir+'/' + replay_dir_prefix  + '.input_trace.'+str(crash_num)+'.txt')
            if os.path.exists(crash_dir+'/crash'+str(crash_num)) == False:
                os.mkdir(crash_dir+'/crash'+str(crash_num))
            shutil.copy(replay_dir+'/input.'+str(num), crash_dir+'/crash'+str(crash_num) + '/input')
            if os.path.exists('crash_info') == False:
                os.mkdir('crash_info')
            crash_list.append(tc_num)
            sys.stderr.write('start crash test {}\n'.format(crash_gen_path))
       
        crash_data_generator = crash_gen_path + os.sep + 'crash_gen_with_harness_gen'
        crash_test_cmd = crash_data_generator + ' ' + replay_dir_prefix + ' ' + crash_gen_path[:-3] +'CROWN_tc_generator'
        sys.stderr.write('Crash Info Gen Cmd: {}\n'.format(crash_test_cmd))
        os.system(crash_test_cmd)
        self.state = ''
        sys.stderr.write('crash: {}\n'.format(crash_list))
        return crash_list



    def run_crownc(self, compiler_path, target_directory, file_name, func_name):
        driver_name = file_name[:len(file_name)-4] + '.' + func_name + '.driver.c'
        if not os.path.isfile(driver_name):
            return -6

        if os.path.exists(file_name[:len(file_name)-4] + '.' + func_name + '.driver') and os.path.exists(file_name[:len(file_name)-4] + '.' + func_name + '.driver_replay'):
            sys.stderr.write('Skip Compile\n')
            return 0

        if file_name.find(' ') != -1:
            compile_cmd = compiler_path + ' ./\"' + driver_name + '\" > log/{}.{}.compiler.log 2>&1'.format(file_name[:-4],func_name)
        else:
            compile_cmd = compiler_path + ' ./' + driver_name + ' > log/{}.{}.compiler.log 2>&1'.format(file_name[:-4],func_name)
        print(compile_cmd)
        os.system(compile_cmd)
        if self.crownc_error_check(driver_name[:len(driver_name)-2]) != 0:
            if file_name.find(' ') != -1:
                compile_cmd = compiler_path + '2 ./\"' + driver_name + '\" > log/{}.{}.compiler.log 2>&1'.format(file_name[:-4],func_name)
            else:
                compile_cmd = compiler_path + '2 ./' + driver_name + ' > log/{}.{}.compiler.log 2>&1'.format(file_name[:-4],func_name)
            os.system(compile_cmd)
        return self.crownc_error_check(driver_name[:len(driver_name)-2])

    def run_afl_crownc(self, compiler_path, target_directory, file_name, func_name):
        os.environ['AFLCC']='/home/backend/AFLplusplus/afl-gcc'
        driver_name = file_name[:len(file_name)-4] + '.' + func_name + '.driver.c'
        if not os.path.isfile(driver_name):
            return -6
        if file_name.find(' ') != -1:
            compile_cmd = compiler_path + ' ./\"' + driver_name + '\" > log/{}.{}.fuzzer.log 2>&1'.format(file_name[:-4],func_name)
        else:
            compile_cmd = compiler_path + ' ./' + driver_name + ' > log/{}.{}.fuzzer.log 2>&1'.format(file_name[:-4],func_name)
        print(compile_cmd)
        os.system(compile_cmd)
        if not os.path.exists(file_name[:len(file_name)-4] + '.' + func_name + '.driver_fuzz'):
            sys.stderr.write('Fail to Generate {}.{}.driver_fuzz'.format(file_name[:len(file_name)-4],func_name))
            return -1
        return 0

    def crownc_error_check(self,driver_name):
        if not os.path.isfile(driver_name + '.i') or os.path.getsize(driver_name + '.i') == 0 :
            sys.stderr.write('Driver preprocessing error with ' + driver_name +'\n')
            return -1
        elif not os.path.isfile(driver_name + '.cil.c') or os.path.getsize(driver_name + '.cil.c') == 0:
            sys.stderr.write('Cil processing failed with ' + driver_name + '\n')
            return -2
        elif not os.path.isfile(driver_name + '.cil.i') or os.path.getsize(driver_name + '.cil.i') == 0 :
            sys.stderr.write('Cil preprocessing error with ' + driver_name + '.cil.c\n')
            return -3
        elif not os.path.isfile(driver_name) or os.path.getsize(driver_name) == 0 :
            sys.stderr.write('Driver gen failed with ' + driver_name +'\n')
            return -4
        elif not os.path.isfile(driver_name + '_replay') or os.path.getsize(driver_name +'_replay' ) == 0 :
            sys.stderr.write('Replay gen failed with ' + driver_name[:len(driver_name)-2]+ '_replay\n')
            return -5
        else:
            sys.stderr.write('Compile success with ' + driver_name +'\n')
            return 0

    def crown_tc_gen(self, tc_gen_path, target_directory, file_name, func_name, strategy, execution_timeout, function_timeout, max_test, send_conn, stop_flag):
        self.state = 'crown_tc_gen:'+strategy
        send_conn.send(self.state)
        test_target = file_name[:len(file_name)-4] + '.' + func_name + '.driver'
        test_cmd = 'timeout -s SIGKILL {} ./{}'.format(str(execution_timeout),test_target)
        result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + strategy
        if max_test == 0:
            max_test = 1000000
        if strategy == 'AFL':
            seed_dir = '{}.{}.seed'.format(file_name[:len(file_name)-4], func_name)
            if not os.path.exists(seed_dir):
                os.makedirs(seed_dir)
            with open ('{}/input'.format(seed_dir), 'wb') as file:
                file.write(b'\x00' * 100000)
            afl_target_program = './{}.{}.driver_fuzz'.format(file_name[:len(file_name)-4], func_name)
            afl_path = '/home/backend/AFLplusplus/afl-fuzz'
            afl_environment = 'AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 AFL_SKIP_CPUFREQ=1 AFL_SKIP_CRASHES=1'
            tc_gen_command = '{} timeout -s SIGTERM -k 10s {} {} -i {} -o {} -- {} @@ > log/{}.{}.fuzzing.log 2>&1'.format(afl_environment, function_timeout ,afl_path, seed_dir, result_dir, afl_target_program, file_name[:-4],func_name)
            
            sys.stderr.write('Command: {}\n'.format(tc_gen_command))
            ret = os.system(tc_gen_command)
            if ret >> 8 == 137 and stop_flag.value == True:
                sys.stderr.write('Process is Killed\n')
                self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)
                send_conn.send('user stop')
                self.state = ''
                return (0,0,0,False,'User Stopped')


            self.state = ''
            tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
            sys.stderr.write('Return Value: {}\n'.format(ret))
            if len(tcs) == 0:
                return (0,0,0,False,'Tc gen failed.(Timeout1)')
            elif ret>>8 == 124:
                self.timeout_reached = True
                return (len(tcs),0,0, True, 'FunctionTimeout')
            else:
                return (len(tcs),0,0, False, 'Tc gen success')
        elif strategy == 'AFL Combined':
            timeout = int(function_timeout)/2
            result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.AFL'
            seed_dir = '{}.{}.seed'.format(file_name[:len(file_name)-4], func_name)
            if not os.path.exists(seed_dir):
                os.makedirs(seed_dir)
            with open ('{}/input'.format(seed_dir), 'wb') as file:
                #file.writelines(['0\n' for x in range(100000)])
                file.write(b'\x00' * 100000)
            #os.environ['AFL_PATH']='/home/backend/AFLplusplus/'
            #os.environ['AFL_SKIP_CRASHES'] = '1'
            afl_target_program = './{}.{}.driver_fuzz'.format(file_name[:len(file_name)-4], func_name)
            afl_path = '/home/backend/AFLplusplus/afl-fuzz'
            afl_environment = 'AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 AFL_SKIP_CPUFREQ=1 AFL_SKIP_CRASHES=1'
            tc_gen_command = '{} timeout -s SIGTERM -k 10s {} {} -i {} -o {} -- {} @@ > log/{}.{}.fuzzing.log 2>&1'.format(afl_environment, timeout ,afl_path, seed_dir, result_dir, afl_target_program, file_name[:-4],func_name)

            sys.stderr.write('Command: {}\n'.format(tc_gen_command))
            ret = os.system(tc_gen_command)
            if ret >> 8 == 137 and stop_flag.value == True:
                sys.stderr.write('Process is Killed\n')
                self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)
                send_conn.send('user stop')
                self.state = ''
                return (0,0,0,False,'User Stopped')

            timeout = int(function_timeout)/8
            for substrategy in ['dfs','rev-dfs','cfg','random']:
                result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + substrategy
                tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {} > log/{}.{}.tc_generator.log 2>&1 '.format(timeout, tc_gen_path,test_cmd, max_test, substrategy, result_dir, file_name[:-4],func_name)
                #tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {}'.format(str(execution_timeout), tc_gen_path,test_cmd, max_test, strategy, result_dir)
                sys.stderr.write('Command: {}\n'.format(tc_gen_command))
                ret = os.system(tc_gen_command)
                if ret >> 8 == 137 and stop_flag.value == True:
                    sys.stderr.write('Process is Killed\n')
                    self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)
                    send_conn.send('user stop')
                    self.state = ''
                    return (0,0,0,False,'User Stopped')
                                                                                            
            self.state = ''
            total_tcs = 0
            for substrategy in ['dfs','rev-dfs','cfg','random']:
                result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + substrategy
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                total_tcs = total_tcs + len(tcs)
            tcs = sorted([x for x in os.listdir(file_name[:len(file_name)-4] + '.' + func_name + '.AFL/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(file_name[:len(file_name)-4] + '.' + func_name + '.AFL/default/crashes') if x.startswith('id:')], reverse=True)
            total_tcs = total_tcs + len(tcs)
            return (total_tcs,0,0, False, 'Tc gen success')
        elif strategy == 'combinedSS':
            timeout = int(function_timeout)/4
            for substrategy in ['dfs','rev-dfs','cfg','random']:
                result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + substrategy
                tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {} > log/{}.{}.tc_generator.log 2>&1 '.format(timeout, tc_gen_path,test_cmd, max_test, substrategy, result_dir, file_name[:-4],func_name)
                #tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {}'.format(str(execution_timeout), tc_gen_path,test_cmd, max_test, strategy, result_dir)
                sys.stderr.write('Command: {}\n'.format(tc_gen_command))
                ret = os.system(tc_gen_command)
                if ret >> 8 == 137 and stop_flag.value == True:
                    sys.stderr.write('Process is Killed\n')
                    self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)

                    send_conn.send('user stop')
                    self.state = ''
                    return (0,0,0,False,'User Stopped')
            self.state = ''
            total_tcs = 0
            for substrategy in ['dfs','rev-dfs','cfg','random']:
                result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + substrategy
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                total_tcs = total_tcs + len(tcs)
            return (total_tcs,0,0, False, 'Tc gen success')
        else:
            if os.path.isfile('branches') == False:
                open('branches','w').close()
            tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {} > log/{}.{}.tc_generator.log 2>&1 '.format(function_timeout, tc_gen_path,test_cmd, max_test, strategy, result_dir, file_name[:-4],func_name)
            sys.stderr.write('Command: {}\n'.format(tc_gen_command))
            ret = os.system(tc_gen_command)
            if ret >> 8 == 137 and stop_flag.value == True:
                sys.stderr.write('Process is Killed\n')
                self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)

                send_conn.send('user stop')
                self.state = ''
                return (0,0,0,False,'User Stopped')

            
            self.state = ''
            if not os.path.exists(result_dir):
                return(0,0,0, False, 'Tc gen failed.(Timeout1)')
            tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)

            sys.stderr.write('Return Value: {}\n'.format(ret))
            if len(tcs) == 0:
                return (0,0,0,False,'Tc gen failed.(Timeout1)')
            elif ret>>8 == 124:
                self.timeout_reached = True
                return (len(tcs),0,0, True, 'FunctionTimeout')
            else:
                return (len(tcs),0,0, False, 'Tc gen success')

    def user_tc_gen(self, tc_gen_path, target_directory, file_name, func_name, strategy, execution_timeout, function_timeout, max_test, tc_file ,send_conn, stop_flag):
        #self.state = 'crown_tc_gen:'+strategy
        #send_conn.send(self.state)
        test_target = file_name[:len(file_name)-4] + '.' + func_name + '.driver'
        test_cmd = 'timeout -s SIGKILL {} ./{}'.format(str(execution_timeout),test_target)
        strategy_num = len([x for x in os.listdir(os.getcwd()) if x.startswith(file_name[:len(file_name)-4] + '.' + func_name + '.' + strategy)])+1
        self.state = 'crown_tc_gen:'+strategy + str(strategy_num)
        send_conn.send(self.state)
        result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + strategy + str(strategy_num)
        if max_test == 0:
            max_test = 1000000
        if strategy == 'AFL':
            seed_dir = '{}.{}.seed'.format(file_name[:len(file_name)-4], func_name)
            if not os.path.exists(seed_dir):
                os.makedirs(seed_dir)
            #with open ('{}/input'.format(seed_dir), 'wb') as file:
            #                                                                                                                                                    file.write(b'\x00' * 100000)
            afl_target_program = './{}.{}.driver_fuzz'.format(file_name[:len(file_name)-4], func_name)
            afl_path = '/home/backend/AFLplusplus/afl-fuzz'
            afl_environment = 'AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 AFL_SKIP_CPUFREQ=1 AFL_SKIP_CRASHES=1'
            tc_gen_command = '{} timeout -s SIGTERM -k 10s {} {} -i {} -o {} -- {} @@ > log/{}.{}.fuzzing.log 2>&1'.format(afl_environment, function_timeout ,afl_path, seed_dir, result_dir, afl_target_program, file_name[:-4],func_name)
            sys.stderr.write('Command: {}\n'.format(tc_gen_command))
            ret = os.system(tc_gen_command)
            if ret >> 8 == 137 and stop_flag.value == True:
                sys.stderr.write('Process is Killed\n')
                self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)
                send_conn.send('user stop')
                self.state = ''
                return (0,0,0,False,'User Stopped')


            self.state = ''
            tcs = sorted([x for x in os.listdir(result_dir+'/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(result_dir+'/default/crashes') if x.startswith('id:')], reverse=True)
            sys.stderr.write('Return Value: {}\n'.format(ret))
            if len(tcs) == 0:
                return (0,0,0,False,'Tc gen failed.(Timeout1)')
            elif ret>>8 == 124:
                self.timeout_reached = True
                return (len(tcs),0,0, True, 'FunctionTimeout')
            else:
                return (len(tcs),0,0, False, 'Tc gen success')
        elif strategy == 'AFL Combined':
            timeout = int(function_timeout)/2
            result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.AFL'
            seed_dir = '{}.{}.seed'.format(file_name[:len(file_name)-4], func_name)
            if not os.path.exists(seed_dir):
                os.makedirs(seed_dir)
            #with open ('{}/input'.format(seed_dir), 'wb') as file:
            #    #file.writelines(['0\n' for x in range(100000)])
            #    file.write(b'\x00' * 100000)
            #os.environ['AFL_PATH']='/home/backend/AFLplusplus/'
            #os.environ['AFL_SKIP_CRASHES'] = '1'
            afl_target_program = './{}.{}.driver_fuzz'.format(file_name[:len(file_name)-4], func_name)
            afl_path = '/home/backend/AFLplusplus/afl-fuzz'
            afl_environment = 'AFL_I_DONT_CARE_ABOUT_MISSING_CRASHES=1 AFL_SKIP_CPUFREQ=1 AFL_SKIP_CRASHES=1'
            tc_gen_command = '{} timeout -s SIGTERM -k 10s {} {} -i {} -o {} -- {} @@ > log/{}.{}.fuzzing.log 2>&1'.format(afl_environment, timeout ,afl_path, seed_dir, result_dir, afl_target_program, file_name[:-4],func_name)
            
            sys.stderr.write('Command: {}\n'.format(tc_gen_command))
            ret = os.system(tc_gen_command)
            if ret >> 8 == 137 and stop_flag.value == True:
                sys.stderr.write('Process is Killed\n')
                self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)
                send_conn.send('user stop')
                self.state = ''
                return (0,0,0,False,'User Stopped')

            timeout = int(function_timeout)/8
            for substrategy in ['dfs','rev-dfs','cfg','random']:
                result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + substrategy
                tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {} -INIT_TC > log/{}.{}.tc_generator.log 2>&1 '.format(timeout, tc_gen_path,test_cmd, max_test, substrategy, result_dir, file_name[:-4],func_name)
                #tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {}'.format(str(execution_timeout), tc_gen_path,test_cmd, max_test, strategy, result_dir)
                sys.stderr.write('Command: {}\n'.format(tc_gen_command))
                ret = os.system(tc_gen_command)
                if ret >> 8 == 137 and stop_flag.value == True:
                    sys.stderr.write('Process is Killed\n')
                    self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)
                    send_conn.send('user stop')
                    self.state = ''
                    return (0,0,0,False,'User Stopped')
            self.state = ''
            total_tcs = 0
            for substrategy in ['dfs','rev-dfs','cfg','random']:
                AddTC.addInputTC(tc_file, os.getcwd())
                result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + substrategy
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                total_tcs = total_tcs + len(tcs)
                tcs = sorted([x for x in os.listdir(file_name[:len(file_name)-4] + '.' + func_name + '.AFL/default/queue') if x.startswith('id:')], reverse=True) + sorted([x for x in os.listdir(file_name[:len(file_name)-4] + '.' + func_name + '.AFL/default/crashes') if x.startswith('id:')], reverse=True)
                total_tcs = total_tcs + len(tcs)
            return (total_tcs,0,0, False, 'Tc gen success')
        elif strategy == 'combinedSS':
            timeout = int(function_timeout)/4
            for substrategy in ['dfs','rev-dfs','cfg','random']:
                AddTC.addInputTC(tc_file, os.getcwd())
                result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + substrategy
                tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {} -INIT_TC > log/{}.{}.tc_generator.log 2>&1 '.format(timeout, tc_gen_path,test_cmd, max_test, substrategy, result_dir, file_name[:-4],func_name)
                #tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {}'.format(str(execution_timeout), tc_gen_path,test_cmd, max_test, strategy, result_dir)
                sys.stderr.write('Command: {}\n'.format(tc_gen_command))
                ret = os.system(tc_gen_command)
                if ret >> 8 == 137 and stop_flag.value == True:
                    sys.stderr.write('Process is Killed\n')
                    self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)
                    send_conn.send('user stop')
                    self.state = ''
                    return (0,0,0,False,'User Stopped')
            self.state = ''
            total_tcs = 0
            for substrategy in ['dfs','rev-dfs','cfg','random']:
                result_dir = file_name[:len(file_name)-4] + '.' + func_name + '.' + substrategy
                tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
                total_tcs = total_tcs + len(tcs)
                return (total_tcs,0,0, False, 'Tc gen success')
        else:
            AddTC.addInputTC(tc_file, os.getcwd())
            if os.path.isfile('branches') == False:
                open('branches','w').close()
            tc_gen_command = 'timeout -s SIGTERM -k 10s {} {} "{}" {} -{} -TCDIR {} -INIT_TC > log/{}.{}.tc_generator.log 2>&1 '.format(function_timeout, tc_gen_path,test_cmd, max_test, strategy, result_dir, file_name[:-4],func_name)
            sys.stderr.write('Command: {}\n'.format(tc_gen_command))
            ret = os.system(tc_gen_command)
            if ret >> 8 == 137 and stop_flag.value == True:
                sys.stderr.write('Process is Killed\n')
                self.delete_test_data(os.getcwd() , file_name[:len(file_name)-4], func_name)
                send_conn.send('user stop')
                self.state = ''
                return (0,0,0,False,'User Stopped')

            self.state = ''
            if not os.path.exists(result_dir):
                return(0,0,0, False, 'Tc gen failed.(Timeout1)')
            tcs = sorted([x for x in os.listdir(result_dir) if x.startswith('input.')], reverse=True)
            sys.stderr.write('Return Value: {}\n'.format(ret))
            if len(tcs) == 0:
                return (0,0,0,False,'Tc gen failed.(Timeout1)')
            elif ret>>8 == 124:
                self.timeout_reached = True
                return (len(tcs),0,0, True, 'FunctionTimeout')
            else:
                return (len(tcs),0,0, False, 'Tc gen success')


    def get_hash(self, filename, first_chunk_only=False, hash_algo=hashlib.sha256):
        hashobj = hash_algo()
        with open(filename, 'rb') as file:
            if first_chunk_only:
                hashobj.update(file.read(1024))
            else:
                for chunk in self.chunk_reader(file):
                    hashobj.update(chunk)
        return hashobj.digest()

    def check_for_duplicates(self, path, unique_path ,correct):
        files_by_size = defaultdict(list)
        files_by_small_hash = defaultdict(list)
        files_by_full_hash = dict()
        target_files = []

        if not path.endswith('combinedSS'):
            paths = (unique_path ,path)
            sys.stderr.write('iterate path: {}\n'.format(paths))
            for dirpath, _, filenames in chain.from_iterable(os.walk(path) for path in paths) :
            #for dirpath, _, filenames in os.walk(path):
                for filename in filenames:
                    #sys.stderr.write('file: {}\n'.format(filename))
                    if correct == True and filename.startswith('input.') == False:
                        continue
                    if correct == False and filename.startswith('timeout1reached_input.') == False:
                        continue
                    full_path = os.path.join(dirpath, filename)
                    try:
                        full_path = os.path.realpath(full_path)
                        file_size = os.path.getsize(full_path)
                    except OSError:
                        continue
                    files_by_size[file_size].append(full_path)
        else:
            paths = (unique_path ,path[:-10]+'dfs' , path[:-10]+'rev-dfs', path[:-10]+'cfg', path[:-10]+'random')

            for dirpath, _, filenames in chain.from_iterable(os.walk(path) for path in paths) :
                for filename in filenames:
                    if correct == True and filename.startswith('input.') == False:
                        continue
                    if correct == False and filename.startswith('timeout1reached_input.') == False:
                        continue
                    full_path = os.path.join(dirpath, filename)
                    try:
                        full_path = os.path.realpath(full_path)
                        file_size = os.path.getsize(full_path)
                    except OSError:
                        continue
                    files_by_size[file_size].append(full_path)
        for file_size, files in files_by_size.items():
            if len(files) < 1:
                continue
            elif len(files) == 1:
                target_files = target_files + files
                continue
            for filename in files:
                try:
                    small_hash = self.get_hash(filename, first_chunk_only=True)
                except OSError:
                    continue
                files_by_small_hash[(file_size, small_hash)].append(filename)
        for files in files_by_small_hash.values():
            if len(files) < 1:
                continue
            elif len(files) == 1:
                target_files = target_files + files
                continue
            for filename in files:
                try:
                    full_hash = self.get_hash(filename, first_chunk_only=False)
                except OSError:
                    continue

                if full_hash in files_by_full_hash and not filename.startswith(unique_path):
                    duplicate = files_by_full_hash[full_hash]
                else:
                    files_by_full_hash[full_hash] = filename
                    target_files.append(filename)
        return target_files

    def copy_files(self, target_folder, file_list, timeout):
            
        if os.path.exists(target_folder) == False:
            os.mkdir(target_folder)
            
        num = 1
        if timeout == False:
            for path in os.listdir(target_folder):
                if os.path.isfile(os.path.join(target_folder, path)) and path.startswith('input.'):
                    num += 1
        sys.stderr.write('unique tc num: {}\n'.format(num))

        file_list.sort(key=lambda f: int(re.sub('\D', '', f)))
        for file_name in file_list:
            if timeout == False:
                if file_name.startswith(target_folder):
                    #sys.stderr.write('Skip {}\n'.format(file_name))
                    continue
                shutil.copy(file_name, os.path.join(target_folder, "input."+str(num)))
                if os.path.exists(file_name.replace('input.','type.')):
                    shutil.copy(file_name.replace('input.','type.'), os.path.join(target_folder, "type."+str(num)))
            else:
                shutil.copy(file_name, os.path.join(target_folder, "timeout_input."+str(num)))
            num = num+1


    def chunk_reader(self, fobj, chunk_size=1024):
        while True:
            chunk = fobj.read(chunk_size)
            if not chunk:
                return
            yield chunk

    def convert_afl_to_crown(self, src_dir, target_dir):
        if src_dir.endswith('AFL Combined'):
            src_dir = src_dir[:-9]
        _,_, files = next(os.walk(target_dir))
        num = len(files)
        for file in os.listdir(src_dir + os.sep + 'default/queue'):
            if os.path.isfile(src_dir + os.sep + 'default/queue' + os.sep + file):
                num = num +1
                shutil.copy(src_dir + os.sep + 'default/queue' + os.sep + file, target_dir + os.sep + 'input.' + str(num))
        
        for file in os.listdir(src_dir + os.sep + 'default/crashes'):
            if os.path.isfile(src_dir + os.sep + 'default/crashes' + os.sep + file):
                num = num +1
                shutil.copy(src_dir + os.sep + 'default/crashes' + os.sep + file, target_dir + os.sep + 'input.' + str(num))

    def run_duplicate_remove(self, file_name, func_name, strategy, num_total_tc, send_conn):
        if self.timeout_reached == True:
            self.state = 'duplicate_remove with timeout'
        else:
            self.state = 'duplicate_remove'
        send_conn.send(self.state)
        correct_target_folder = file_name[:len(file_name)-4] + '.' + func_name + '.unique'
        timeout_target_folder = file_name[:len(file_name)-4] + '.' + func_name + '.timeout'

        sys.stderr.write('correct target folder: {} timeout_target_folder: {}\n'.format(correct_target_folder, timeout_target_folder))
        
        # rename unique directory to temp if exists
        #if os.path.exists(correct_target_folder):
        #    sys.stderr.write('rename {} to input_backup\n'.format(correct_target_folder))
        #    os.rename(correct_target_folder, "input_backup")
        #else:
        #    os.mkdir("input_backup")
        if not os.path.exists(correct_target_folder):
            os.mkdir(correct_target_folder)

        tc_folder = file_name[:len(file_name)-4] + '.' + func_name + '.' + strategy

        target_files = self.check_for_duplicates(tc_folder, correct_target_folder, True)
        self.copy_files(os.path.join(os.getcwd(), correct_target_folder), target_files, False)
        target_files = self.check_for_duplicates(tc_folder, correct_target_folder, False)
        self.copy_files(os.path.join(os.getcwd(), timeout_target_folder), target_files, True)
        sys.stderr.write('run_duplicate_remove end\n')
        
        if strategy == 'AFL' or strategy == 'AFL Combined':
            self.convert_afl_to_crown(tc_folder, correct_target_folder)

        #if os.path.exists("input_backup"):
        #    shutil.rmtree('input_backup')
        self.state = ''
        
        tcs = sorted([x for x in os.listdir(correct_target_folder) if x.startswith('input.')], reverse=True)
        return (num_total_tc, len(tcs), 0, 'Unique gen success')


    def run_replay(self, file_name, func_name, iter_start, iter_end, execution_timeout, crash_gen_path, array_size, send_conn, stop_flag):
        self.state = 'run_replay'
        if os.path.exists('log/{}.{}.replay.log'.format(file_name[:-4],func_name)):
            os.remove('log/{}.{}.replay.log'.format(file_name[:-4],func_name))
        send_conn.send(self.state)
        replay_dir = file_name[:len(file_name)-4] + '.' + func_name + '.unique'
        replay_target = './' + file_name[:len(file_name)-4] + '.' + func_name + '.driver_replay'
        replay_cmd = 'timeout -s SIGTERM -k ' + str(execution_timeout +5 ) + ' --preserve-status ' + str(execution_timeout) + ' ' + replay_target +' >> log/{}.{}.replay.log 2>&1'.format(file_name[:-4],func_name)
        if os.path.isfile('.CROWN.input_trace.txt'):
            print('Removing: .CROWN.input_trace.txt')
            os.remove('.CROWN.input_trace.txt')
        fileList = glob.glob('.CROWN.input_trace.*.txt')

        for file in fileList:
            try:
                os.remove(file)
            except:
                print("Fail to remove : "+file)

        crash_num = 1
        replay_dir_prefix = replay_dir[:-7]
        crash_dir = replay_dir_prefix + '.crash'
        source_file = file_name 
        crash_prefix = crash_dir + os.sep + file_name[:len(file_name)-4] + '.' + func_name + '.crashtc'
        crash_input_prefix = crash_dir + os.sep + file_name[:len(file_name)-4] + '.' + func_name + '.input_trace.'
        original_file = os.getcwd().replace('/output/','/src/') + os.sep + file_name[:-2]
        crash_array_size = array_size
        self.crash_list = []
        for num in range(iter_start, iter_end+1):
            os.environ["CROWN_TC_FILE"] = replay_dir+'/input.'+str(num)
            print('CROWN_TC_FILE: ' + os.environ["CROWN_TC_FILE"])
            shutil.copy(replay_dir+'/input.'+str(num), 'input')
            ret = subprocess.run(replay_cmd, shell=True)
            print("Iteration " + str(num) + "  Return value: " + str(ret) )
            print("----------------------")
            #if os.path.isfile('.CROWN.input_trace.txt') == True and ret.returncode != 0:
            if os.path.isfile('.CROWN.input_trace.txt'):
                sys.stderr.write('Crash with input.'+str(num))
                sys.stderr.write('Crash dir: {}\n'.format(crash_dir))
                if os.path.exists(crash_dir) == False:
                    os.mkdir(crash_dir)
                sys.stderr.write('Source File: {}\n'.format(source_file))
                if os.path.exists(source_file) and not os.path.exists(crash_dir + os.sep + source_file) :
                    shutil.copy(source_file, crash_dir)
                sys.stderr.write('Original File: {}\n'.format(original_file))
                if os.path.exists(original_file) and not os.path.exists(crash_dir + os.sep + original_file) :
                    shutil.copy(original_file, crash_dir)
                os.rename('.CROWN.input_trace.txt', crash_dir+'/' + replay_dir_prefix  + '.input_trace.'+str(crash_num)+'.txt')
                if os.path.exists(crash_dir+'/crash'+str(crash_num)) == False:
                    os.mkdir(crash_dir+'/crash'+str(crash_num))
                shutil.copy(replay_dir+'/input.'+str(num), crash_dir+'/crash'+str(crash_num) + '/input')
                if os.path.exists('crash_info') == False:
                    os.mkdir('crash_info')
                #sys.stderr.write('start crash test {}\n'.format(crash_gen_path))
                #crash_tc_generator_path = crash_gen_path[:crash_gen_path.rfind('/')+1] + 'crown_crashtc_generator'
                #sys.stderr.write('crash_tc_generator_path: {}\n'.format(crash_tc_generator_path))
                #crash_test_cmd = crash_gen_path + ' ' + crash_tc_generator_path + ' ' + source_file + ' ' + crash_prefix + ' ' + func_name + ' ' + crash_input_prefix + ' ' + str(array_size) + ' temp.log'
                #sys.stderr.write('crash_tc_gen cmd: {}\n'.format(crash_test_cmd))
                #rtn = os.system(crash_test_cmd)
                if stop_flag.value == True:
                    sys.stderr.write('Stop TC Gen\n')
                    self.delete_test_data('', file_name[:len(file_name)-4], func_name)
                    return []
                crash_num = crash_num + 1
                self.crash_list.append(num)
            if stop_flag.value == True:
                sys.stderr.write('Stop Replay\n')
                self.delete_test_data('', file_name[:len(file_name)-4], func_name)
                return []
        if stop_flag.value == False:
            sys.stderr.write('start crash test {}\n'.format(crash_gen_path))
            '''
            crash_tc_generator_path = crash_gen_path[:crash_gen_path.rfind('/')+1] + 'crown_crashtc_generator'
            sys.stderr.write('crash_tc_generator_path: {}\n'.format(crash_tc_generator_path))
            crash_test_cmd = crash_gen_path + ' ' + crash_tc_generator_path + ' ' + source_file + ' ' + crash_prefix + ' ' + func_name + ' ' + crash_input_prefix + ' ' + str(array_size) + ' temp.log'
            sys.stderr.write('crash_tc_gen cmd: {}\n'.format(crash_test_cmd))
            rtn = os.system(crash_test_cmd)
            '''
            crash_data_generator = crash_gen_path[:crash_gen_path.rfind('/')+1] + 'crash_gen_with_harness_gen'

            crash_test_cmd = crash_data_generator + ' ' + replay_dir_prefix + ' ' + crash_gen_path[:crash_gen_path.rfind('/')-3] +'CROWN_tc_generator'
            sys.stderr.write('Crash Info Gen Cmd: {}\n'.format(crash_test_cmd))
            os.system(crash_test_cmd)
        self.state = ''
        sys.stderr.write('crash: {}\n'.format(self.crash_list))
        return self.crash_list

    def run_single_function_tc_generator(self, tc_generator_path, target_dir, file_location, file_name, func_name, strategy, executionTimeout, functionTimeout, maxTest, useSanitizer, func_id, tc_gen_queue, send_conn, stop_flag , array_size = 1, max_array_size = 10 ):
        
        if file_name == '' or func_name == '':
            sys.stderr.write('Wrong request with file_name: ' + file_name + ' func_name: ' + func_name + '\n')
            tc_gen_queue.put_nowait((func['id'],  {'uniqueTC': 0, 'allTC':0, 'crashTC': 0, 'functionTimeout': None, 'status':'TC_gen_failed'}))
            return
       

        target_directory = target_dir + os.sep + file_location
        cur_dir = os.getcwd()

        self.file_path = target_directory + os.sep+ file_name[:len(file_name)-4] + '.' + func_name
        send_conn.send(self.file_path)
        self.func_id = func_id
        self.strategy = strategy
        self.execution_timeout = executionTimeout
        self.function_timeout = functionTimeout
        self.max_test = maxTest
        self.use_sanitizer = useSanitizer
        self.status = 'Init'
        self.delete_test_data(target_directory, file_name[:len(file_name)-4], func_name)

        sys.stderr.write('target directory: ' + target_directory + '\n')
        os.chdir(target_directory)
        
        sys.stderr.write('move dir to ' + os.getcwd() + '\n')
        compiler_path = tc_generator_path + 'crown_compiler'
        fuzzer_path = tc_generator_path + 'crown_fuzz_compiler'
     
        if self.run_crownc(compiler_path, target_dir, file_name, func_name) <0:
            sys.stderr.write('Run Crownc Failed\n')
            self.status = ''
            self.state = 'Driver Compile Failed'
            #tc_gen_queue.put_nowait((-1, -1, -1, self.timeout_reached, 'Driver Compile Failed'))
            send_conn.send(self.state)
            os.chdir(cur_dir)
            return
        if strategy == 'AFL' or strategy == 'AFL Combined':
            if self.run_afl_crownc(fuzzer_path, target_dir, file_name, func_name) < 0:
                sys.stderr.write('Run Afl Compile Failed\n')
                self.status = ''
                self.state = 'Driver Compile Failed'
                send_conn.send(self.state)
                os.chdir(cur_dir)
                return
        tc_gen_path = tc_generator_path + 'crown_tc_generator'
        crash_gen_path = tc_generator_path + 'crash_gen'
        total_tc, unique_tc, crash_tc, timeout, comment = self.crown_tc_gen(tc_gen_path, target_dir, file_name, func_name, strategy, executionTimeout, functionTimeout, maxTest, send_conn= send_conn, stop_flag = stop_flag)
        if comment == 'User Stopped':
            sys.stderr.write('User Stopped: {}.{}\n'.format(file_name, func_name))
            os.chdir(cur_dir)
            return
        elif total_tc == 0:
            sys.stderr.write('TC gen failed with timeout: {}.{}\n'.format(file_name, func_name))
            tc_gen_queue.put_nowait((-1, -1, -1, True, 'TC gen failed with timeout'))
            send_conn.send('Stop')
            os.chdir(cur_dir)
            return
        
        else:
            sys.stderr.write('Total TC is {}. run duplicate remove...\n'.format(str(total_tc)))
        
        num = 1
        if os.path.exists(self.file_path+'.unique'):
            for path in os.listdir(self.file_path+'.unique'):
                if os.path.isfile(os.path.join( self.file_path+'.unique', path)) and path.startswith('input.'):
                    num += 1

        _, unique_tc, _, comment = self.run_duplicate_remove(file_name, func_name, strategy, total_tc, send_conn = send_conn)
        sys.stderr.write('Unique TC is {}, run replay...\n'.format(str(unique_tc)))
        
        crash_tcs = self.run_replay(file_name, func_name, num, unique_tc, functionTimeout, crash_gen_path, array_size, send_conn = send_conn, stop_flag = stop_flag)
        sys.stderr.write('crash list: {}\n'.format(crash_tcs))
        if stop_flag.value == True:
            send_conn.send('user stop')
            self.state = ''
            sys.stderr.write('User Stopped: {}.{}\n'.format(file_name, func_name))
            os.chdir(cur_dir)
            return
        sys.stderr.write('Crash TC is {}.\n'.format(str(len(crash_tcs))))
        crash_tc = len(crash_tcs)

        csv_cmd = tc_generator_path + os.sep + 'make_csv ' + self.file_path + '.unique'
        sys.stderr.write('csv_cmd: {}\n'.format(csv_cmd))
        os.system(csv_cmd)
        
        os.chdir(cur_dir)
        self.status = ''
        self.state = ''
        #tc_gen_queue.put_nowait((total_tc,unique_tc, crash_tc, timeout, 'Success'))
        send_conn.send('success')
        self.generate_json_data(target_directory, file_name[:-4], func_name, crash_tcs, array_size)

    
    def run_add_tc_generator(self, tc_generator_path, target_dir, file_location, file_name, func_name, strategy, executionTimeout, functionTimeout, maxTest, useSanitizer, input_tc, func_id, tc_gen_queue, send_conn, stop_flag, array_size = 1, max_array_size = 10 ):

        if file_name == '' or func_name == '':
            sys.stderr.write('Wrong request with file_name: ' + file_name + ' func_name: ' + func_name + '\n')
            tc_gen_queue.put_nowait((func['id'],  {'uniqueTC': 0, 'allTC':0, 'crashTC': 0, 'functionTimeout': None, 'status':'TC_gen_failed'}))
            return


        strategy_num = len([x for x in os.listdir(os.getcwd()) if x.startswith(file_name[:len(file_name)-4] + '.' + func_name + '.' + strategy)])
        self.strategy = strategy + str(strategy_num)
        target_directory = target_dir + os.sep + file_location
        cur_dir = os.getcwd()

        self.file_path = target_directory + os.sep+ file_name[:len(file_name)-4] + '.' + func_name
        send_conn.send(self.file_path)
        self.func_id = func_id
        #self.strategy = strategy
        self.execution_timeout = executionTimeout
        self.function_timeout = functionTimeout
        self.max_test = maxTest
        self.use_sanitizer = useSanitizer
        self.status = 'Init'
        self.delete_test_data(target_directory, file_name[:len(file_name)-4], func_name)
        sys.stderr.write('target directory: ' + target_directory + '\n')
        os.chdir(target_directory)
        sys.stderr.write('move dir to ' + os.getcwd() + '\n')
        #compiler_path = tc_generator_path + 'crown_compiler'
        #fuzzer_path = tc_generator_path + 'crown_fuzz_compiler'

        #if strategy == 'AFL' or strategy == 'AFL Combined':
        #    if self.run_afl_crownc(fuzzer_path, target_dir, file_name, func_name) < 0:
        #        sys.stderr.write('Run Afl Compile Failed\n')
        #        self.status = ''
        #        self.state = 'Driver Compile Failed'
        #        send_conn.send(self.state)
        #        os.chdir(cur_dir)
        #        return
        tc_gen_path = tc_generator_path + 'crown_tc_generator'
        crash_gen_path = tc_generator_path + 'crash_gen'
        total_tc, unique_tc, crash_tc, timeout, comment = self.user_tc_gen(tc_gen_path, target_dir, file_name, func_name, strategy, executionTimeout, functionTimeout, maxTest, input_tc, send_conn= send_conn, stop_flag = stop_flag)
        if comment == 'User Stopped':
            sys.stderr.write('User Stopped: {}.{}\n'.format(file_name, func_name))
            os.chdir(cur_dir)
            return
        elif total_tc == 0:
            sys.stderr.write('TC gen failed with timeout: {}.{}\n'.format(file_name, func_name))
            tc_gen_queue.put_nowait((-1, -1, -1, True, 'TC gen failed with timeout'))
            send_conn.send('Stop')
            os.chdir(cur_dir)
            return
        else:
            sys.stderr.write('Total TC is {}. run duplicate remove...\n'.format(str(total_tc)))
        num = 1
        if os.path.exists(self.file_path+'.unique'):
            for path in os.listdir(self.file_path+'.unique'):
                if os.path.isfile(os.path.join( self.file_path+'.unique', path)) and path.startswith('input.'):
                    num += 1

        strategy_num = len([x for x in os.listdir(os.getcwd()) if x.startswith(file_name[:len(file_name)-4] + '.' + func_name + '.' + strategy)])
        strategy = strategy + str(strategy_num)
        _, unique_tc, _, comment = self.run_duplicate_remove(file_name, func_name, strategy, total_tc, send_conn = send_conn)
        sys.stderr.write('Unique TC is {}, run replay...\n'.format(str(unique_tc)))

        #file_name = file_name + ',i'
        crash_tcs = self.run_replay(file_name, func_name, num, unique_tc, functionTimeout, crash_gen_path, array_size, send_conn = send_conn, stop_flag = stop_flag)
        sys.stderr.write('crash list: {}\n'.format(crash_tcs))
        if stop_flag.value == True:
            send_conn.send('user stop')
            self.state = ''
            sys.stderr.write('User Stopped: {}.{}\n'.format(file_name, func_name))
            os.chdir(cur_dir)
            return
        sys.stderr.write('Crash TC is {}.\n'.format(str(len(crash_tcs))))
        crash_tc = len(crash_tcs)

        csv_cmd = tc_generator_path + os.sep + 'make_csv ' + self.file_path + '.unique'
        sys.stderr.write('csv_cmd: {}\n'.format(csv_cmd))
        os.system(csv_cmd)

        os.chdir(cur_dir)
        self.status = ''
        self.state = ''
        #tc_gen_queue.put_nowait((total_tc,unique_tc, crash_tc, timeout, 'Success'))
        send_conn.send('success')
        self.generate_json_data(target_directory, file_name[:-4], func_name, crash_tcs, array_size)
    
