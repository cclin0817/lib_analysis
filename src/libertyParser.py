import os
import re
import sys
import time
import datetime
import collections
from typing import List, Dict, Any, Optional

os.environ["PYTHONUNBUFFERED"] = "1"


# Liberty parser (start) #
class libertyParser():
    """
    Parse liberty file and save a special dictionary data structure.
    Get specified data with sub-function "getData".
    """
    def __init__(self, libFile: str, cellList: List[str] = [], debug: bool = False):
        self.debug = debug

        self.debugPrint(f'* Liberty File : {libFile}')

        # Liberty file must exists.
        if not os.path.exists(libFile):
            print(f'*Error*: liberty file "{libFile}": No such file!', file=sys.stderr)
            sys.exit(1)

        # Pre-compile regexes for performance
        self._group_re = re.compile(r'^(\s*)(\S+)\s*\((.*?)\)\s*{\s*$')
        self._group_done_re = re.compile(r'^\s*}\s*$')
        self._simple_attr_re = re.compile(r'^(\s*)(\S+)\s*:\s*(.+)\s*;.*$')
        self._special_simple_attr_re = re.compile(r'^(\s*)(\S+)\s*:\s*(.+)\s*$')
        self._complex_attr_re = re.compile(r'^(\s*)(\S+)\s*(\(.+\))\s*;.*$')
        self._special_complex_attr_re = re.compile(r'^(\s*)(\S+)\s*(\(.+\))\s*$')
        self._multilines_re = re.compile(r'^(.*)\\s*$')
        self._multilines_done_re = re.compile(r'^(.*;)\s*$')
        self._comment_start_re = re.compile(r'^(\s*)/\*.*$')
        self._comment_end_re = re.compile(r'.*\*/\s*$')
        self._empty_line_re = re.compile(r'^\s*$')


        # If cellList is specified, regenerate the cell-based liberty file as libFile.
        if len(cellList) > 0:
            self.debugPrint(f'* Specified Cell List : {cellList}')
            libFile = self.genCellLibFile(libFile, cellList)

        # Parse the liberty file and organize the data structure as a dictionary.
        groupList = self.libertyParser(libFile)
        self.libDic = self.organizeData(groupList)

    def debugPrint(self, message: str):
        """
        Print debug message.
        """
        if self.debug:
            currentTime = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            print(f'DEBUG [{currentTime}]: {message}')

    def genCellLibFile(self, libFile: str, cellList: List[str]) -> str:
        """
        For big liberty files with multi-cells, it will cost too much time to parse the liberty file.
        This function is used to generate a new liberty file only contains the specified cells,
        so it can save a lot of time on liberty file parsering.
        This implementation is in pure Python to ensure portability.
        """
        cellNames = '_'.join(cellList)
        cellLibFile = f"{libFile}.{cellNames}"
        self.debugPrint(f'>>> Generating cell-based liberty file "{cellLibFile}" ...')

        cell_locations = collections.OrderedDict()
        cell_re = re.compile(r'^\s*cell\s*\((.*?)\)\s*{\s*$')
        comment_start_re = re.compile(r'^\s*/\*')
        comment_end_re = re.compile(r'\*/\s*$')

        self.debugPrint(f'    Getting cells from liberty file "{libFile}" ...')
        in_comment = False
        with open(libFile, 'r') as f:
            for i, line in enumerate(f, 1):
                if in_comment:
                    if comment_end_re.search(line):
                        in_comment = False
                    continue
                if comment_start_re.match(line):
                    if not comment_end_re.search(line):
                        in_comment = True
                    continue
                
                match = cell_re.match(line)
                if match:
                    cell_name = match.group(1).strip()
                    if cell_name.startswith('"') and cell_name.endswith('"'):
                        cell_name = cell_name[1:-1]
                    cell_locations[cell_name] = i
        
        all_cells_in_file = list(cell_locations.keys())

        # Make sure all the specified cells are on libFile.
        self.debugPrint('    Check specified cells missing or not.')
        missing_cells = [cell for cell in cellList if cell not in all_cells_in_file]
        if missing_cells:
            for cell in missing_cells:
                print(f'*Error*: cell "{cell}" is not in liberty file "{libFile}".', file=sys.stderr)
            sys.exit(1)

        self.debugPrint('    Writing cell-based liberty file...')
        with open(libFile, 'r') as f_in, open(cellLibFile, 'w') as f_out:
            all_lines = f_in.readlines()

            # Write header part
            first_cell_line_num = cell_locations[all_cells_in_file[0]]
            f_out.writelines(all_lines[:first_cell_line_num - 1])

            # Write cell parts
            for cell in cellList:
                cell_start_line = cell_locations[cell]
                cell_index = all_cells_in_file.index(cell)
                
                if cell_index == len(all_cells_in_file) - 1:
                    # Last cell in the original file
                    cell_end_line = len(all_lines)
                else:
                    next_cell = all_cells_in_file[cell_index + 1]
                    cell_end_line = cell_locations[next_cell]

                self.debugPrint(f'    Writing cell "{cell}" ...')
                f_out.writelines(all_lines[cell_start_line - 1 : cell_end_line -1 if cell_index != len(all_cells_in_file) - 1 else cell_end_line])

            # Add closing brace for the library definition
            f_out.write('}\n')

        return cellLibFile

    def getLastOpenedGroupNum(self, openedGroupNumList: List[int]) -> int:
        """
        All of the new attribute data are saved on last opened group, so need to get the last opened group num.
        """
        if openedGroupNumList:
            return openedGroupNumList[-1]
        return -1

    def libertyParser(self, libFile: str) -> List[Dict[str, Any]]:
        """
        Parse liberty file line in line.
        Save data block based on "group".
        Save data blocks into a list.
        """
        multiLinesString = ''
        commentMark = False
        groupList: List[Dict[str, Any]] = []
        groupListNum = 0
        openedGroupNumList: List[int] = []
        lastOpenedGroupNum = -1

        self.debugPrint(f'>>> Parsing liberty file "{libFile}" ...')
        startSeconds = int(time.time())
        libFileLine = 0

        with open(libFile, 'r') as LF:
            for line in LF:
                libFileLine += 1

                if commentMark:
                    if self._comment_end_re.match(line):
                        commentMark = False
                    continue

                if self._multilines_re.match(line):
                    myMatch = self._multilines_re.match(line)
                    currentLineContent = myMatch.group(1)
                    multiLinesString += currentLineContent
                    continue
                
                if multiLinesString:
                    if self._multilines_done_re.match(line):
                        myMatch = self._multilines_done_re.match(line)
                        currentLineContent = myMatch.group(1)
                        line = multiLinesString + currentLineContent
                    else:
                        print(f'*Error*: Line {libFileLine}: multi-lines is not finished rightly!', file=sys.stderr)
                        print(f'         {line.strip()}', file=sys.stderr)
                        multiLinesString = ''
                        continue
                
                # Sort by compile hit rate.
                if self._complex_attr_re.match(line):
                    myMatch = self._complex_attr_re.match(line)
                    key = myMatch.group(2)
                    valueList = myMatch.group(3)

                    if key in groupList[lastOpenedGroupNum]:
                        if isinstance(groupList[lastOpenedGroupNum][key], list):
                            groupList[lastOpenedGroupNum][key].append(valueList)
                        else:
                            groupList[lastOpenedGroupNum][key] = [groupList[lastOpenedGroupNum][key], valueList]
                    else:
                        groupList[lastOpenedGroupNum][key] = valueList
                elif self._simple_attr_re.match(line):
                    myMatch = self._simple_attr_re.match(line)
                    key = myMatch.group(2)
                    value = myMatch.group(3)
                    groupList[lastOpenedGroupNum][key] = value
                elif self._group_re.match(line):
                    myMatch = self._group_re.match(line)
                    groupDepth = len(myMatch.group(1))
                    groupType = myMatch.group(2)
                    groupName = myMatch.group(3)

                    lastOpenedGroupNum = self.getLastOpenedGroupNum(openedGroupNumList)

                    currentGroupDic = {
                                       'fatherGroupNum': lastOpenedGroupNum,
                                       'depth': groupDepth,
                                       'type': groupType,
                                       'name': groupName,
                                      }

                    groupList.append(currentGroupDic)
                    openedGroupNumList.append(groupListNum)
                    groupListNum += 1
                    lastOpenedGroupNum = self.getLastOpenedGroupNum(openedGroupNumList)
                elif self._group_done_re.match(line):
                    openedGroupNumList.pop()
                    lastOpenedGroupNum = self.getLastOpenedGroupNum(openedGroupNumList)
                elif self._comment_start_re.match(line):
                    if not self._comment_end_re.match(line):
                        commentMark = True
                elif self._empty_line_re.match(line):
                    pass
                elif self._special_complex_attr_re.match(line):
                    print(f'*Warning*: Line {libFileLine}: Irregular liberty line!', file=sys.stderr)
                    print(f'          {line.strip()}', file=sys.stderr)
                    myMatch = self._special_complex_attr_re.match(line)
                    key = myMatch.group(2)
                    valueList = myMatch.group(3)

                    if key in groupList[lastOpenedGroupNum]:
                        if isinstance(groupList[lastOpenedGroupNum][key], list):
                            groupList[lastOpenedGroupNum][key].append(valueList)
                        else:
                            groupList[lastOpenedGroupNum][key] = [groupList[lastOpenedGroupNum][key], valueList]
                    else:
                        groupList[lastOpenedGroupNum][key] = valueList
                elif self._special_simple_attr_re.match(line):
                    print(f'*Warning*: Line {libFileLine}: Irregular line!', file=sys.stderr)
                    print(f'          {line.strip()}', file=sys.stderr)
                    myMatch = self._special_simple_attr_re.match(line)
                    key = myMatch.group(2)
                    value = myMatch.group(3)
                    groupList[lastOpenedGroupNum][key] = value
                else:
                    print(f'*Error*: Line {libFileLine}: Unrecognizable line!', file=sys.stderr)
                    print(f'         {line.strip()}', file=sys.stderr)

                if multiLinesString:
                    multiLinesString = ''

        endSeconds = int(time.time())
        parseSeconds = endSeconds - startSeconds
        self.debugPrint('    Done')
        self.debugPrint(f'    Parse time : {libFileLine} lines, {parseSeconds} seconds.')

        return groupList

    def organizeData(self, groupList: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Re-organize list data structure (groupList) into a dictionary data structure.
        """
        self.debugPrint('>>> Re-organizing data structure ...')

        for i in range(len(groupList)-1, 0, -1):
            groupDic = groupList[i]
            fatherGroupNum = groupDic['fatherGroupNum']
            if fatherGroupNum != -1:
                groupList[fatherGroupNum].setdefault('group', [])
                groupList[fatherGroupNum]['group'].insert(0, groupDic)

        self.debugPrint('    Done')

        return groupList[0]
# Liberty parser (end) #

# Verification functions (start) #
    def restoreLib(self, libFile: str):
        """
        This function is used to verify the liberty parser.
        It converts self.libDic into the original liberty file (comment will be ignored).
        Please save the output message into a file, then compare it with the original liberty file.
        """
        with open(libFile, 'w') as f:
            self._restoreLib(f, self.libDic)

    def _restoreLib(self, f, groupDic: Dict[str, Any]):
        """
        Recursively writes group dictionary to the file object.
        """
        groupDepth = groupDic['depth']
        groupType = groupDic['type']
        groupName = groupDic['name']

        f.write(f"{' '*groupDepth}{groupType} ({groupName}) {{\n")

        for key, value in groupDic.items():
            if key in ('fatherGroupNum', 'depth', 'type', 'name'):
                continue
            
            if key == 'group':
                subGroupList = groupDic['group']
                for subGroup in subGroupList:
                    self._restoreLib(f, subGroup)
            elif key == 'values':
                f.write(f"{'  '*groupDepth}  {key} ( \\n")
                valueString = re.sub(r'\(|\)', '', value)
                valueString = re.sub(r'"\s*,\s*"', '"#"', valueString)
                valuesList = re.split('#', valueString)

                for i, item in enumerate(valuesList):
                    item = item.strip()
                    if i == len(valuesList)-1:
                        f.write(f"{'    '*groupDepth}    {item} \\n")
                    else:
                        f.write(f"{'    '*groupDepth}    {item}, \\n")
                f.write(f"{'  '*groupDepth}  );\n")
            elif key == 'table':
                valueString = value.replace('"', '')
                valueList = [v.strip() for v in valueString.split(',')]
                f.write(f"{'  '*groupDepth}  {key} : \"{valueList[0]}, \\n")

                for i in range(1, len(valueList)):
                    item = valueList[i]
                    if i == len(valueList)-1:
                        f.write(f'{item}";\n')
                    else:
                        f.write(f'{item}, \\n')
            elif isinstance(value, list):
                for item in value:
                    if re.match(r'\(.+\)', item):
                        if key == 'define':
                            f.write(f"{'  '*groupDepth}  {key}{item};\n")
                        else:
                            f.write(f"{'  '*groupDepth}  {key} {item};\n")
                    else:
                        f.write(f"{'  '*groupDepth}  {key} : {item};\n")
            else:
                if re.match(r'\(.+\)', str(value)):
                    f.write(f"{'  '*groupDepth}  {key} {value};\n")
                else:
                    f.write(f"{'  '*groupDepth}  {key} : {value};\n")

        f.write(f"{' '*groupDepth}}}\n")
# Verification functions (end) #

# Application functions (start) #
    def getUnit(self) -> Dict[str, Any]:
        """
        Get all "unit" setting.
        Return a dict.
        """
        unitDic = collections.OrderedDict()
        for key, value in self.libDic.items():
            if key.endswith('_unit'):
                unitDic[key] = value
        return unitDic

    def getCellList(self) -> List[str]:
        """
        Get all cells.
        Return a list.
        """
        cellList = []
        if 'group' in self.libDic:
            for libGroupDic in self.libDic['group']:
                if libGroupDic.get('type') == 'cell':
                    cellList.append(libGroupDic['name'])
        return cellList

    def getCellArea(self, cellList: List[str] = []) -> Dict[str, Any]:
        """
        Get cell area information for specified cell list.
        Return a dict.
        """
        cellAreaDic = collections.OrderedDict()
        if 'group' in self.libDic:
            for groupDic in self.libDic['group']:
                if groupDic.get('type') == 'cell':
                    cellName = groupDic['name']
                    if not cellList or cellName in cellList:
                        cellAreaDic[cellName] = groupDic.get('area', '')
        
        for cellName in cellList:
            if cellName not in cellAreaDic:
                cellAreaDic[cellName] = ''
        return cellAreaDic

    def getCellLeakagePower(self, cellList: List[str] = []) -> Dict[str, List[Dict[str, Any]]]:
        """
        Get cell leakage_power information for specified cell list.
        Return a dict.
        """
        cellLeakagePowerDic = collections.OrderedDict()
        if 'group' in self.libDic:
            for groupDic in self.libDic['group']:
                if groupDic.get('type') == 'cell':
                    cellName = groupDic['name']
                    if not cellList or cellName in cellList:
                        if 'group' in groupDic:
                            for cellGroupDic in groupDic['group']:
                                if cellGroupDic.get('type') == 'leakage_power':
                                    leakagePowerDic = {
                                        key: value for key, value in cellGroupDic.items() 
                                        if key in ('value', 'when', 'related_pg_pin')
                                    }
                                    cellLeakagePowerDic.setdefault(cellName, []).append(leakagePowerDic)
        return cellLeakagePowerDic

    def _getTimingGroupInfo(self, groupDic: Dict[str, Any]) -> Dict[str, Any]:
        """
        Split pin timing information from the pin timing dict.
        """
        timingDic = collections.OrderedDict()
        if groupDic.get('type') != 'timing':
            return timingDic

        for key in ['related_pin', 'related_pg_pin', 'timing_sense', 'timing_type', 'when']:
            if key in groupDic:
                timingDic[key] = groupDic[key]

        if 'group' in groupDic:
            timingDic['table_type'] = collections.OrderedDict()
            for timingLevelGroupDic in groupDic['group']:
                timingLevelGroupType = timingLevelGroupDic['type']
                timingDic['table_type'][timingLevelGroupType] = collections.OrderedDict()
                
                if timingLevelGroupDic.get('name'):
                    timingDic['table_type'][timingLevelGroupType]['template_name'] = timingLevelGroupDic['name']

                for key in ['sigma_type', 'index_1', 'index_2', 'values']:
                     if key in timingLevelGroupDic:
                        timingDic['table_type'][timingLevelGroupType][key] = timingLevelGroupDic[key]
        return timingDic

    def _getInternalPowerGroupInfo(self, groupDic: Dict[str, Any]) -> Dict[str, Any]:
        """
        Split pin internal_power information from the pin internal_power dict.
        """
        internalPowerDic = collections.OrderedDict()
        if groupDic.get('type') != 'internal_power':
            return internalPowerDic

        for key in ['related_pin', 'related_pg_pin', 'when']:
            if key in groupDic:
                internalPowerDic[key] = groupDic[key]

        if 'group' in groupDic:
            internalPowerDic['table_type'] = collections.OrderedDict()
            for internalPowerLevelGroupDic in groupDic['group']:
                internalPowerLevelGroupType = internalPowerLevelGroupDic['type']
                internalPowerDic['table_type'][internalPowerLevelGroupType] = collections.OrderedDict()
                for key in ['index_1', 'index_2', 'values']:
                    if key in internalPowerLevelGroupDic:
                        internalPowerDic['table_type'][internalPowerLevelGroupType][key] = internalPowerLevelGroupDic[key]
        return internalPowerDic

    def _getPinInfo(self, groupDic: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Split cell pin timing/internal_power information from pin dict.
        """
        pinDic: Dict[str, List[Dict[str, Any]]] = collections.OrderedDict()
        if groupDic.get('type') == 'pin' and 'group' in groupDic:
            for pinGroupDic in groupDic['group']:
                pinGroupType = pinGroupDic['type']
                if pinGroupType == 'timing':
                    timingDic = self._getTimingGroupInfo(pinGroupDic)
                    pinDic.setdefault('timing', []).append(timingDic)
                elif pinGroupType == 'internal_power':
                    internalPowerDic = self._getInternalPowerGroupInfo(pinGroupDic)
                    pinDic.setdefault('internal_power', []).append(internalPowerDic)
        return pinDic

    def _getBundleInfo(self, groupDic: Dict[str, Any], pinList: List[str] = []) -> Dict[str, Any]:
        """
        Split bundle pin timing/internal_power information from the bundle dict.
        """
        bundleDic = collections.OrderedDict()
        if 'members' in groupDic:
            pinListString = re.sub(r'[\(")\s]', '', groupDic['members'])
            pins = pinListString.split(',')
            bundleDic.setdefault('pin', collections.OrderedDict())
            for pinName in pins:
                bundleDic['pin'].setdefault(pinName.strip(), collections.OrderedDict())

        if 'group' in groupDic:
            for subGroupDic in groupDic['group']:
                groupType = subGroupDic['type']
                if groupType == 'pin':
                    pinName = subGroupDic['name']
                    if pinList and pinName not in pinList:
                        continue
                    bundleDic.setdefault('pin', collections.OrderedDict())
                    pinDic = self._getPinInfo(subGroupDic)
                    if pinDic:
                        bundleDic['pin'][pinName] = pinDic
                elif groupType == 'timing':
                    timingDic = self._getTimingGroupInfo(subGroupDic)
                    bundleDic.setdefault('timing', []).append(timingDic)
                elif groupType == 'internal_power':
                    internalPowerDic = self._getInternalPowerGroupInfo(subGroupDic)
                    bundleDic.setdefault('internal_power', []).append(internalPowerDic)
        return bundleDic

    def _getBusInfo(self, groupDic: Dict[str, Any], pinList: List[str] = []) -> Dict[str, Any]:
        """
        Split bus pin timing/internal_power information from the bus dict.
        """
        busDic = collections.OrderedDict()
        if 'group' in groupDic:
            for subGroupDic in groupDic['group']:
                groupType = subGroupDic['type']
                if groupType == 'pin':
                    pinName = subGroupDic['name']
                    if pinList and pinName not in pinList:
                        continue
                    busDic.setdefault('pin', collections.OrderedDict())
                    pinDic = self._getPinInfo(subGroupDic)
                    if pinDic:
                        busDic['pin'][pinName] = pinDic
                elif groupType == 'timing':
                    timingDic = self._getTimingGroupInfo(subGroupDic)
                    busDic.setdefault('timing', []).append(timingDic)
                elif groupType == 'internal_power':
                    internalPowerDic = self._getInternalPowerGroupInfo(subGroupDic)
                    busDic.setdefault('internal_power', []).append(internalPowerDic)
        return busDic

    def getLibPinInfo(self, cellList: List[str] = [], bundleList: List[str] = [], busList: List[str] = [], pinList: List[str] = []) -> Dict[str, Any]:
        """
        Get all pins (and timing&intern_power info).
        """
        libPinDic = collections.OrderedDict()
        if 'group' not in self.libDic:
            return libPinDic

        for libGroupDic in self.libDic['group']:
            if libGroupDic.get('type') == 'cell':
                cellName = libGroupDic['name']
                if cellList and cellName not in cellList:
                    continue

                if 'group' in libGroupDic:
                    for cellGroupDic in libGroupDic['group']:
                        cellGroupType = cellGroupDic['type']
                        
                        if cellGroupType == 'pin':
                            pinName = cellGroupDic['name']
                            if pinList and pinName not in pinList:
                                continue
                            pinDic = self._getPinInfo(cellGroupDic)
                            if pinDic:
                                libPinDic.setdefault('cell', collections.OrderedDict()).setdefault(cellName, collections.OrderedDict()).setdefault('pin', collections.OrderedDict())[pinName] = pinDic
                        
                        elif cellGroupType == 'bundle':
                            bundleName = cellGroupDic['name']
                            if bundleList and bundleName not in bundleList:
                                continue
                            bundleDic = self._getBundleInfo(cellGroupDic, pinList)
                            if bundleDic:
                                libPinDic.setdefault('cell', collections.OrderedDict()).setdefault(cellName, collections.OrderedDict()).setdefault('bundle', collections.OrderedDict())[bundleName] = bundleDic

                        elif cellGroupType == 'bus':
                            busName = cellGroupDic['name']
                            # Fixed logic error: was checking bundleName in busList
                            if busList and busName not in busList:
                                continue
                            busDic = self._getBusInfo(cellGroupDic, pinList)
                            if busDic:
                                libPinDic.setdefault('cell', collections.OrderedDict()).setdefault(cellName, collections.OrderedDict()).setdefault('bus', collections.OrderedDict())[busName] = busDic
        return libPinDic
# Application functions (end) #