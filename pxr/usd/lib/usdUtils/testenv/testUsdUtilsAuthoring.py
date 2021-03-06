#!/pxrpythonsubst
#
# Copyright 2017 Pixar
#
# Licensed under the Apache License, Version 2.0 (the "Apache License")
# with the following modification; you may not use this file except in
# compliance with the Apache License and the following modification to it:
# Section 6. Trademarks. is deleted and replaced with:
#
# 6. Trademarks. This License does not grant permission to use the trade
#    names, trademarks, service marks, or product names of the Licensor
#    and its affiliates, except as required to comply with Section 4(c) of
#    the License and to reproduce the content of the NOTICE file.
#
# You may obtain a copy of the Apache License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the Apache License with the above modification is
# distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
# KIND, either express or implied. See the Apache License for the specific
# language governing permissions and limitations under the Apache License.
from pxr import UsdUtils, Sdf, Usd
import unittest

class TestUsdUtilsAuthoring(unittest.TestCase):
    def test_CopyLayerMetadata(self):
        # Test CopyLayerMetadata()
        source = Sdf.Layer.FindOrOpen('layerWithMetadata.usda')
        self.assertTrue(source)

        keysToCompare = [x for x in source.pseudoRoot.ListInfoKeys() if 
                         (x not in ['subLayers', 'subLayerOffsets'])]

        cpy = Sdf.Layer.CreateNew("cpy.usda")
        self.assertTrue(cpy)
        UsdUtils.CopyLayerMetadata(source, cpy)
        
        for key in ['subLayers'] + keysToCompare:
            self.assertEqual(source.pseudoRoot.GetInfo(key),
                             cpy.pseudoRoot.GetInfo(key))
        # bug #127687 - can't use GetInfo() for subLayerOffsets
        self.assertEqual(source.subLayerOffsets, cpy.subLayerOffsets)

        cpyNoSublayers = Sdf.Layer.CreateNew("cpyNoSublayers.usda")
        self.assertTrue(cpyNoSublayers)
        UsdUtils.CopyLayerMetadata(source, cpyNoSublayers, skipSublayers=True, 
            bakeUnauthoredFallbacks=True)
        self.assertFalse(cpyNoSublayers.pseudoRoot.HasInfo('subLayers'))
        self.assertFalse(cpyNoSublayers.pseudoRoot.HasInfo('subLayerOffsets'))
        for key in keysToCompare:
            self.assertEqual(source.pseudoRoot.GetInfo(key),
                             cpyNoSublayers.pseudoRoot.GetInfo(key))
        
        # Ensure that the color config fallbacks get stamped out when
        # bakeUnauthoredFallbacks is set to true.
        fallbackKeysToCompare = ['colorConfiguration', 'colorManagementSystem']
        colorConfigFallbacks = Usd.Stage.GetColorConfigFallbacks()
        self.assertEqual(colorConfigFallbacks,
            (cpyNoSublayers.pseudoRoot.GetInfo(Sdf.Layer.ColorConfigurationKey), 
             cpyNoSublayers.pseudoRoot.GetInfo(Sdf.Layer.ColorManagementSystemKey)))

    def test_CreateCollections(self):
        carPaths = [Sdf.Path('/World/City_set/Vehicles_grp/Cars_grp/CarA'),
                    Sdf.Path('/World/City_set/Vehicles_grp/Cars_grp/CarB'),
                    Sdf.Path('/World/City_set/Vehicles_grp/Cars_grp/CarC'),
                    ]
        bikePaths = [Sdf.Path('/World/City_set/Vehicles_grp/Bikes_grp/BikeA'),
                     Sdf.Path('/World/City_set/Vehicles_grp/Bikes_grp/BikeB'),
                     Sdf.Path('/World/City_set/Vehicles_grp/Bikes_grp/BikeC'),
                     Sdf.Path('/World/City_set/Vehicles_grp/Bikes_grp/BikeD')
                    ]
        otherVehiclePaths = [Sdf.Path('/World/City_set/Misc_grp/TruckA'),
                             Sdf.Path('/World/City_set/Misc_grp/BicycleA')]

        stage = Usd.Stage.Open("collections.usda")
        self.assertTrue(stage)

        city_set = stage.GetPrimAtPath("/World/City_set")
        self.assertTrue(city_set)

        vehicles_grp = stage.GetPrimAtPath("/World/City_set/Vehicles_grp")
        self.assertTrue(vehicles_grp)

        assignments = [('vehicles:cars', carPaths),
                       ('vehicles:bikes', bikePaths),
                       ('vehicles:other', otherVehiclePaths)]

        collections = UsdUtils.CreateCollections(assignments, vehicles_grp)

        # Verify that the collections that were created have the appropriate 
        # sizes.
        for collection in collections:
            query = collection.ComputeMembershipQuery()
            includedObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                    query, stage)
            includes = collection.GetIncludesRel().GetTargets()
            excludes = collection.GetExcludesRel().GetTargets()

            if collection.GetName() == "vehicles:cars":
                # Ensure that the common ancestor is included.
                self.assertEqual(includes,
                        [Sdf.Path("/World/City_set/Vehicles_grp/Cars_grp")])
                self.assertEqual(excludes, [])
                self.assertEqual(len(includedObjects), 7)
            elif collection.GetName() == "vehicles:bikes":
                self.assertEqual(includes,
                        [Sdf.Path("/World/City_set/Vehicles_grp/Bikes_grp")])
                self.assertEqual(excludes, [])
                self.assertEqual(len(includedObjects), 9)
            elif collection.GetName() == "vehicles:other":
                self.assertEqual(set(includes), set(otherVehiclePaths))
                self.assertEqual(len(includedObjects), 4)

        carPaths.append(Sdf.Path('/World/City_set/Misc_grp/CarD'))

        bikePaths.extend([Sdf.Path('/World/City_set/Misc_grp/BikeE'),
                          Sdf.Path('/World/City_set/Misc_grp/BikeF')])

        # Test case with overlapping paths and collections that
        # have excludes.
        newAssignments = [('vehicles:cars', carPaths),
                           ('vehicles:bikes', bikePaths),
                           ('vehicles:carsOrBikes', carPaths+bikePaths),
                           ('vehicles:others', otherVehiclePaths)]

        newCollections = UsdUtils.CreateCollections(newAssignments, city_set)

        vehicleCarsIncludesAndExcludes = \
            UsdUtils.ComputeCollectionIncludesAndExcludes(carPaths, stage)
        vehicleBikesIncludesAndExcludes = \
            UsdUtils.ComputeCollectionIncludesAndExcludes(bikePaths, stage)
        vehicleCarsOrBikesIncludesAndExcludes = \
            UsdUtils.ComputeCollectionIncludesAndExcludes(
                carPaths + bikePaths, stage)
        vehicleOthersIncludesAndExcludes = \
            UsdUtils.ComputeCollectionIncludesAndExcludes(otherVehiclePaths, 
                stage)

        # Verify that the collections that were created have the appropriate 
        # sizes.
        for collection in newCollections:
            query = collection.ComputeMembershipQuery()
            includedObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                    query, stage)

            includes = collection.GetIncludesRel().GetTargets()
            excludes = collection.GetExcludesRel().GetTargets()

            if collection.GetName() == "vehicles:cars":
                self.assertEqual(vehicleCarsIncludesAndExcludes[0], includes)
                self.assertEqual(vehicleCarsIncludesAndExcludes[1], excludes)

                self.assertTrue(Sdf.Path("/World/City_set/Vehicles_grp")
                                        in includes)
                self.assertTrue(Sdf.Path("/World/City_set/Vehicles_grp/Bikes_grp")                                       
                                        in excludes)
                self.assertEqual(len(includedObjects), 10)
            elif collection.GetName() == "vehicles:bikes":
                self.assertEqual(vehicleBikesIncludesAndExcludes[0], includes)
                self.assertEqual(vehicleBikesIncludesAndExcludes[1], excludes)

                self.assertTrue(Sdf.Path("/World/City_set/Vehicles_grp")
                                        in includes)
                self.assertTrue(Sdf.Path("/World/City_set/Misc_grp")
                                        not in includes)
                self.assertTrue(Sdf.Path("/World/City_set/Vehicles_grp/Cars_grp")
                                        in excludes)
                self.assertEqual(len(includedObjects), 14)
            elif collection.GetName() == "vehicles:carsOrBikes":
                self.assertEqual(vehicleCarsOrBikesIncludesAndExcludes[0], includes)
                self.assertEqual(vehicleCarsOrBikesIncludesAndExcludes[1], excludes)

                self.assertTrue(Sdf.Path("/World/City_set")
                                        in includes)
                self.assertTrue(Sdf.Path("/World/City_set/Misc_grp/BicycleA")
                                        in excludes)
                self.assertTrue(Sdf.Path("/World/City_set/Misc_grp/TruckA")
                                        in excludes)

            elif collection.GetName() == "vehicles:other":
                self.assertEqual(vehicleOthersIncludesAndExcludes[0], includes)
                self.assertEqual(vehicleOthersIncludesAndExcludes[1], excludes)
                self.assertEqual(len(includedObjects), 4)

        furniturePaths = [Sdf.Path('/World/Room_set/Table_grp/Table'),
                          Sdf.Path('/World/Room_set/Chairs_grp/ChairA'),
                          Sdf.Path('/World/Room_set/Chairs_grp/ChairB')]
        
        penOrPencilPaths = [Sdf.Path('/World/Room_set/Table_grp/Pencils_grp/PencilA'),
                            Sdf.Path('/World/Room_set/Table_grp/Pencils_grp/PencilB'),
                            Sdf.Path('/World/Room_set/Table_grp/Pencils_grp/PencilC'),
                            Sdf.Path('/World/Room_set/Table_grp/Pens_grp/PenA'),
                            Sdf.Path('/World/Room_set/Table_grp/Pens_grp/PenB')]
        
        assignments = [('furniture', furniturePaths),
                       ('pensOrPencils', penOrPencilPaths),
                       ('emptyCollection', [])]

        rootCollections = UsdUtils.CreateCollections(assignments, 
                stage.GetPrimAtPath("/World"))

        # 'emptyCollection' is still created but has no includes or excludes.
        self.assertEqual(len(rootCollections), 3)

        for collection in rootCollections:
            query = collection.ComputeMembershipQuery()
            includedObjects = Usd.CollectionAPI.ComputeIncludedObjects(
                    query, stage)
            
            includes = collection.GetIncludesRel().GetTargets()
            excludes = collection.GetExcludesRel().GetTargets()
            
            if collection.GetName() == 'pensOrPencils':
                self.assertTrue(Sdf.Path('/World/Room_set/Table_grp/Pencils_grp') 
                                in includes)
                self.assertTrue(Sdf.Path('/World/Room_set/Table_grp/Pens_grp') 
                                in includes)
                self.assertTrue(Sdf.Path('/World/Room_set/Table_grp/Pencils_grp/EraserA') 
                                in excludes)
            elif collection.GetName() == "furniture":
                self.assertTrue(Sdf.Path('/World/Room_set/Chairs_grp') in includes)
                self.assertTrue(Sdf.Path('/World/Room_set/Table_grp/Table') in includes)
                self.assertEqual(len(excludes), 0)
            elif collection.GetName() == "emptyCollection":
                self.assertEqual(len(includes), 0)
                self.assertEqual(len(excludes), 0)

        # Test creation of collections with instance paths.
        lampBasePaths = [Sdf.Path('/World/Room_set/Table_grp/LampA/Geom/Base'),
                         Sdf.Path('/World/Room_set/Table_grp/LampB/Geom/Base'),
                         Sdf.Path('/World/Room_set/Table_grp/LampC/Geom/Base')]
        lampShadePaths = [Sdf.Path('/World/Room_set/Table_grp/LampA/Geom/Shade'),
                         Sdf.Path('/World/Room_set/Table_grp/LampB/Geom/Shade'),
                         Sdf.Path('/World/Room_set/Table_grp/LampC/Geom/Shade')]

        assignments = [('lampBases', lampBasePaths),
                       ('lampShades', lampShadePaths)]
        lampCollections = UsdUtils.CreateCollections(assignments, 
                stage.GetPrimAtPath("/World/Room_set"))

        for collection in lampCollections:
            query = collection.ComputeMembershipQuery()
            includedPaths = Usd.CollectionAPI.ComputeIncludedPaths(
                    query, stage, Usd.TraverseInstanceProxies())

            if collection.GetName() == 'lampBases':
                for p in lampBasePaths: 
                    self.assertTrue(p in includedPaths)
            elif collection.GetName() == "lampShades":
                for p in lampShadePaths: 
                    self.assertTrue(p in includedPaths)

        lampAPaths = [Sdf.Path('/World/Room_set/Table_grp/LampA/Geom/Base'),
                      Sdf.Path('/World/Room_set/Table_grp/LampA/Geom/Shade')]
        lampBPaths = [Sdf.Path('/World/Room_set/Table_grp/LampB/Geom/Base'),
                      Sdf.Path('/World/Room_set/Table_grp/LampB/Geom/Shade')]
        lampCPaths = [Sdf.Path('/World/Room_set/Table_grp/LampC/Geom/Base'),
                      Sdf.Path('/World/Room_set/Table_grp/LampC/Geom/Shade')]

        assignments = [('lampA', lampAPaths),
                       ('lampB', lampBPaths),
                       ('lampC', lampCPaths)]
        lampCollections = UsdUtils.CreateCollections(assignments, 
                stage.GetPrimAtPath("/World/Room_set/Table_grp"),
                minIncludeExcludeCollectionSize=2)
            
        for collection in lampCollections:
            query = collection.ComputeMembershipQuery()
            includedPaths = Usd.CollectionAPI.ComputeIncludedPaths(
                    query, stage, Usd.TraverseInstanceProxies())

            if collection.GetName() == 'lampA':
                for p in lampAPaths: 
                    self.assertTrue(p in includedPaths)
            elif collection.GetName() == "lampB":
                for p in lampBPaths: 
                    self.assertTrue(p in includedPaths)
            elif collection.GetName() == "lampC":
                for p in lampCPaths: 
                    self.assertTrue(p in includedPaths)


if __name__=="__main__":
    unittest.main()
