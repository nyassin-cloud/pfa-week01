"""Falling Snow Generator for Maya 2026.

Paste this entire file into Maya's Script Editor Python tab and execute.
Uses polygon flakes and repeating animation curves; no plug-ins required.
Distances use the scene's units. Snow falls along Y (use a Y-up scene).
This is a visual snowfall effect, without collisions or accumulation.
PNG flakes use Standard Surface emission to preserve image colors without lights,
and alpha-driven opacity for Arnold. Keep the PNG alongside the scene files.
Press 6 over the viewport to display textures. Arnold rendering requires MtoA.
"""

import os
import random
import maya.cmds as cmds


class SnowGenerator:
    WINDOW = "studentSnowGeneratorUI"
    TAG = "studentSnowGeneratorOwned"

    def __init__(self):
        self.controls = {}
        if cmds.window(self.WINDOW, exists=True):
            cmds.deleteUI(self.WINDOW)
        cmds.window(self.WINDOW, title="Falling Snow Generator", widthHeight=(460, 560))
        cmds.columnLayout(adjustableColumn=True, rowSpacing=8, columnAttach=("both", 12))
        cmds.text(label="FALLING SNOW", height=30, font="boldLabelFont")
        cmds.text(label="Polygon snow with looping keyframe animation.")
        self.controls["count"] = cmds.intSliderGrp(
            label="Number of flakes", field=True, minValue=10, maxValue=1000, value=200)
        for key, label, minimum, maximum, value in [
            ("width", "Area width (X)", 1, 100, 20),
            ("depth", "Area depth (Z)", 1, 100, 20),
            ("height", "Fall height (Y)", 1, 100, 15),
            ("size", "Flake radius", 0.01, 0.5, 0.08),
            ("wind", "Wind drift (X)", -10, 10, 2),
        ]:
            self.controls[key] = cmds.floatSliderGrp(
                label=label, field=True, minValue=minimum, maxValue=maximum,
                value=value, precision=2)
        self.controls["duration"] = cmds.intSliderGrp(
            label="Frames per fall", field=True, minValue=12, maxValue=240, value=72)
        self.controls["seed"] = cmds.intFieldGrp(label="Random seed", value1=7)
        self.controls["image"] = cmds.textFieldButtonGrp(
            label="Snowflake PNG", buttonLabel="Browse", buttonCommand=self.browse)
        cmds.text(label="Use a PNG with real transparency. Blank = spheres.")
        cmds.text(label="Fewer frames per fall = faster snow.\nChange the seed for a different arrangement.", height=36)
        cmds.button(label="Generate Snow", height=36, command=self.generate)
        cmds.button(label="Select Snow Group", command=self.select_snow)
        cmds.button(label="Clear Snow", command=self.clear)
        self.status = cmds.text(label="Ready. Generate snow, then press Play in Maya.", height=30)
        cmds.showWindow(self.WINDOW)

    def browse(self, *_):
        paths = cmds.fileDialog2(fileMode=1, caption="Choose Snowflake PNG",
                                 fileFilter="PNG Images (*.png)")
        if paths:
            cmds.textFieldButtonGrp(self.controls["image"], edit=True, text=paths[0])

    def groups(self):
        # An explicit marker prevents deleting unrelated objects with similar names.
        return [node for node in (cmds.ls(type="transform", long=True) or [])
                if cmds.attributeQuery(self.TAG, node=node, exists=True)
                and cmds.getAttr(node + "." + self.TAG)]

    def remove_generated(self):
        for group in self.groups():
            owned = cmds.listConnections(group + ".snowResources", source=True,
                                         destination=False) or []
            cmds.delete(group)
            for node in set(owned):
                if cmds.objExists(node):
                    cmds.delete(node)

    def clear(self, *_):
        cmds.undoInfo(openChunk=True, chunkName="Clear Generated Snow")
        try:
            self.remove_generated()
            cmds.text(self.status, edit=True, label="Generated snow cleared.")
        finally:
            cmds.undoInfo(closeChunk=True)

    def select_snow(self, *_):
        groups = self.groups()
        if groups:
            cmds.select(groups, replace=True)
        else:
            cmds.warning("Generate snow first.")

    def generate(self, *_):
        if cmds.upAxis(query=True, axis=True) != "y":
            cmds.warning("This snow generator needs a Y-up scene.")
            return
        values = {key: cmds.floatSliderGrp(self.controls[key], query=True, value=True)
                  for key in ("width", "depth", "height", "size", "wind")}
        count = cmds.intSliderGrp(self.controls["count"], query=True, value=True)
        duration = cmds.intSliderGrp(self.controls["duration"], query=True, value=True)
        seed = cmds.intFieldGrp(self.controls["seed"], query=True, value1=True)
        image_path = cmds.textFieldButtonGrp(self.controls["image"], query=True, text=True).strip()
        if image_path and not os.path.isfile(image_path):
            cmds.warning("The selected image does not exist.")
            return
        if not 1 <= count <= 1000 or duration < 2 or any(
                values[key] <= 0 for key in ("width", "depth", "height", "size")):
            cmds.warning("Use 1-1000 flakes, positive sizes, and at least 2 frames per fall.")
            return
        rng = random.Random(seed)
        start = cmds.playbackOptions(query=True, minTime=True)
        cmds.undoInfo(openChunk=True, chunkName="Generate Falling Snow")
        cmds.refresh(suspend=True)
        try:
            self.remove_generated()
            group = cmds.group(empty=True, name="FallingSnow_GRP#")
            cmds.addAttr(group, longName=self.TAG, attributeType="bool", defaultValue=True)
            cmds.addAttr(group, longName="snowResources", attributeType="message", multi=True)
            material = cmds.shadingNode("standardSurface", asShader=True, name="Snow_MAT#")
            shading = cmds.sets(renderable=True, noSurfaceShader=True, empty=True,
                                name="Snow_SG#")
            cmds.setAttr(material + ".baseColor", 0.95, 0.98, 1.0, type="double3")
            cmds.connectAttr(material + ".outColor", shading + ".surfaceShader")
            resources = [material, shading]
            if image_path:
                texture = cmds.shadingNode("file", asTexture=True, name="Snow_IMAGE#")
                placement = cmds.shadingNode("place2dTexture", asUtility=True, name="Snow_UV#")
                cmds.setAttr(texture + ".fileTextureName", image_path, type="string")
                cmds.setAttr(texture + ".alphaIsLuminance", False)
                cmds.connectAttr(placement + ".outUV", texture + ".uvCoord")
                cmds.connectAttr(placement + ".outUvFilterSize", texture + ".uvFilterSize")
                # Preserve image RGB, with PNG alpha controlling the cutout.
                cmds.connectAttr(texture + ".outColor", material + ".emissionColor")
                cmds.setAttr(material + ".base", 0)
                cmds.setAttr(material + ".specular", 0)
                cmds.setAttr(material + ".emission", 1)
                for channel in ("R", "G", "B"):
                    cmds.connectAttr(texture + ".outAlpha", material + ".opacity" + channel)
                resources.extend([texture, placement])
            for index, node in enumerate(resources):
                cmds.connectAttr(node + ".message", "{}.snowResources[{}]".format(group, index))

            for index in range(count):
                radius = values["size"] * rng.uniform(0.6, 1.4)
                if image_path:
                    cards = [cmds.polyPlane(width=radius * 2, height=radius * 2,
                                           subdivisionsX=1, subdivisionsY=1,
                                           axis=axis, constructionHistory=False)[0]
                             for axis in ((0, 0, 1), (1, 0, 0))]
                    flake = cmds.polyUnite(cards, constructionHistory=False, name="snowflake#")[0]
                    for shape in cmds.listRelatives(flake, shapes=True, fullPath=True) or []:
                        if cmds.attributeQuery("aiOpaque", node=shape, exists=True):
                            cmds.setAttr(shape + ".aiOpaque", False)
                else:
                    flake = cmds.polySphere(name="snowflake#", radius=radius,
                                            subdivisionsX=6, subdivisionsY=4, constructionHistory=False)[0]
                flake = cmds.parent(flake, group)[0]
                cmds.sets(flake, edit=True, forceElement=shading)
                x = rng.uniform(-values["width"] / 2, values["width"] / 2)
                z = rng.uniform(-values["depth"] / 2, values["depth"] / 2)
                fall_frames = duration * rng.uniform(0.8, 1.2)
                # Stagger the cycles so the whole volume already has snow at frame 1.
                first = start - rng.uniform(0, fall_frames)
                last = first + fall_frames
                drift = values["wind"] * rng.uniform(0.7, 1.3)
                for attribute, top, bottom in [
                    ("translateX", x, x + drift),
                    ("translateY", values["height"], -values["size"] * 2),
                    ("translateZ", z, z + rng.uniform(-0.5, 0.5)),
                ]:
                    cmds.setKeyframe(flake, attribute=attribute, time=first, value=top)
                    cmds.setKeyframe(flake, attribute=attribute, time=last, value=bottom)
                    cmds.keyTangent(flake, attribute=attribute, inTangentType="linear", outTangentType="linear")
                    cmds.setInfinity(flake, attribute=attribute, preInfinite="cycle", postInfinite="cycle")
            cmds.select(group, replace=True)
            cmds.currentTime(start)
            cmds.text(self.status, edit=True, label="{} flakes created. Press Play to see snowfall.".format(count))
        finally:
            cmds.refresh(suspend=False)
            cmds.refresh(force=True)
            cmds.undoInfo(closeChunk=True)


snow_generator = SnowGenerator()
