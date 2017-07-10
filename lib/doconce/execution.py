from jupyter_client import MultiKernelManager
from nbformat.v4 import output_from_msg
try:
    from queue import Empty  # Py 3
except ImportError:
    from Queue import Empty # Py 2

def create_kernel_client():
    kernelmanager = MultiKernelManager()
    kernel_client_id = kernelmanager.start_kernel('python3')
    kernel_client_kernel = kernelmanager.get_kernel(kernel_client_id)
    kernel_client = kernel_client_kernel.client()
    kernel_client.start_channels()
    return kernel_client

def run_cell(kernel_client, source, timeout=30, cell_index=0):
    # Adapted from nbconvert.ExecutePreprocessor
    # Copyright (c) IPython Development Team.
    # Distributed under the terms of the Modified BSD License.
    
    msg_id = kernel_client.execute(source)
    # wait for finish, with timeout
    while True:
        try:
            msg = kernel_client.shell_channel.get_msg(timeout=timeout)
        except Empty:
            print("Timeout waiting for execute reply", timeout)
            try:
                exception = TimeoutError
            except NameError:
                exception = RuntimeError
            raise exception("Cell execution timed out")

        if msg['parent_header'].get('msg_id') == msg_id:
            break
        else:
            # not our reply
            continue

    outs = []
    execution_count = None

    while True:
        try:
            # We've already waited for execute_reply, so all output
            # should already be waiting. However, on slow networks, like
            # in certain CI systems, waiting < 1 second might miss messages.
            # So long as the kernel sends a status:idle message when it
            # finishes, we won't actually have to wait this long, anyway.
            msg = kernel_client.iopub_channel.get_msg(timeout=5)
        except Empty:
            print("Timeout waiting for IOPub output")
            break
        if msg['parent_header'].get('msg_id') != msg_id:
            # not an output from our execution
            continue

        msg_type = msg['msg_type']
        print("output:", msg_type)
        content = msg['content']

        # set the prompt number for the input and the output
        if 'execution_count' in content:
            execution_count = content['execution_count']
            # cell['execution_count'] = content['execution_count']

        if msg_type == 'status':
            if content['execution_state'] == 'idle':
                break
            else:
                continue
        elif msg_type == 'execute_input':
            continue
        elif msg_type == 'clear_output':
            outs[:] = []
            # clear display_id mapping for this cell
            # for display_id, cell_map in self._display_id_map.items():
            #     if cell_index in cell_map:
            #         cell_map[cell_index] = []
            continue
        elif msg_type.startswith('comm'):
            continue
        
        display_id = None
        if msg_type in {'execute_result', 'display_data', 'update_display_data'}:
            display_id = msg['content'].get('transient', {}).get('display_id', None)
            # if display_id:
                # self._update_display_id(display_id, msg)
            if msg_type == 'update_display_data':
                # update_display_data doesn't get recorded
                continue

        try:
            out = output_from_msg(msg)
        except ValueError:
            print("unhandled iopub msg: " + msg_type)
            continue
        # if display_id:
            # record output index in:
            #   _display_id_map[display_id][cell_idx]
            # cell_map = self._display_id_map.setdefault(display_id, {})
            # output_idx_list = cell_map.setdefault(cell_index, [])
            # output_idx_list.append(len(outs))

        outs.append(out)

    return outs, execution_count
