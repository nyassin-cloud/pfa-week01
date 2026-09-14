"""Maya 2026 Falling Snow Generator.

Run the complete file in Maya's Script Editor Python tab.
1. Browse for a PNG with real transparency (optional), then Generate Snow.
2. Press 6 over the viewport to show textures; press Play for animation.
3. For Arnold, click Fix Arnold - White or Arnold - Original Image Colors.
   These buttons load MtoA and apply the included fix after snow exists.
   Repeat the selected fix after regenerating snow; restart the render.

Includes the supplied generator, Arnold fix, and original-color restoration.
Image snow uses crossed planes; no collision or accumulation is simulated.
Keep the PNG with your project: Maya references the external image file.
Requires Maya; Arnold buttons require the MtoA plug-in.
"""

import os
import random
import maya.cmds as cmds


class SnowGenerator:
    WINDOW = "fallingSnowGeneratorUI"
    TAG = "fallingSnowTool"

    def __init__(self):
        self.controls = {}

        if cmds.window(self.WINDOW, exists=True):
            cmds.deleteUI(self.WINDOW)

        cmds.window(
            self.WINDOW,
            title="Falling Snow Generator",
            widthHeight=(460, 540)
        )
        cmds.columnLayout(
            adjustableColumn=True,
            rowSpacing=10,
            columnAttach=("both", 12)
        )

        cmds.text(
            label="FALLING SNOW GENERATOR",
            font="boldLabelFont",
            height=30
        )

        self.image_field = cmds.textFieldButtonGrp(
            label="Snowflake PNG",
            buttonLabel="Browse",
            buttonCommand=self.browse_image
        )
        cmds.text(
            label="Choose a transparent PNG. Leave blank for spheres."
        )

        self.controls["count"] = cmds.intSliderGrp(
            label="Snowflake count",
            field=True,
            minValue=10,
            maxValue=1000,
            value=200
        )

        settings = [
            ("width", "Area width", 1, 100, 20),
            ("depth", "Area depth", 1, 100, 20),
            ("height", "Fall height", 1, 100, 15),
            ("size", "Flake radius", 0.01, 1, 0.15),
            ("wind", "Wind drift", -10, 10, 2),
        ]

        for key, label, minimum, maximum, default in settings:
            self.controls[key] = cmds.floatSliderGrp(
                label=label,
                field=True,
                minValue=minimum,
                maxValue=maximum,
                value=default,
                precision=2
            )

        self.controls["duration"] = cmds.intSliderGrp(
            label="Frames per fall",
            field=True,
            minValue=12,
            maxValue=240,
            value=72
        )

        cmds.text(label="Fewer frames per fall = faster snow.")

        cmds.button(
            label="Generate Snow",
            height=35,
            command=self.generate
        )
        cmds.button(label="Select Snow", command=self.select_snow)
        cmds.button(label="Clear Snow", command=self.clear)
        cmds.button(label="Fix Arnold - White", command=lambda *_: fix_snow_for_arnold())
        cmds.button(label="Arnold - Original Image Colors", command=lambda *_: restore_snow_colors())

        self.status = cmds.text(
            label="Generate snow, then press Play.",
            height=30
        )

        cmds.showWindow(self.WINDOW)

    def browse_image(self, *_):
        paths = cmds.fileDialog2(
            caption="Choose a Transparent Snowflake PNG",
            fileMode=1,
            fileFilter="PNG Images (*.png)"
        )
        if paths:
            cmds.textFieldButtonGrp(
                self.image_field,
                edit=True,
                text=paths[0]
            )

    def snow_groups(self):
        groups = []
        for node in cmds.ls(type="transform", long=True) or []:
            if cmds.attributeQuery(self.TAG, node=node, exists=True):
                if cmds.getAttr(node + "." + self.TAG):
                    groups.append(node)
        return groups

    def remove_snow(self):
        for group in self.snow_groups():
            resources = cmds.listConnections(
                group + ".snowResources",
                source=True,
                destination=False
            ) or []

            cmds.delete(group)

            for node in set(resources):
                if cmds.objExists(node):
                    cmds.delete(node)

    def clear(self, *_):
        cmds.undoInfo(openChunk=True, chunkName="Clear Snow")
        try:
            self.remove_snow()
            cmds.text(self.status, edit=True, label="Snow cleared.")
        finally:
            cmds.undoInfo(closeChunk=True)

    def select_snow(self, *_):
        groups = self.snow_groups()
        if groups:
            cmds.select(groups, replace=True)
        else:
            cmds.warning("Generate snow first.")

    def create_material(self, group, image_path):
        material = cmds.shadingNode(
            "lambert", asShader=True, name="Snow_MAT#"
        )
        shading_group = cmds.sets(
            renderable=True,
            noSurfaceShader=True,
            empty=True,
            name="Snow_SG#"
        )
        cmds.connectAttr(
            material + ".outColor",
            shading_group + ".surfaceShader"
        )
        cmds.setAttr(
            material + ".color", 0.95, 0.98, 1.0, type="double3"
        )

        resources = [material, shading_group]

        if image_path:
            texture = cmds.shadingNode(
                "file", asTexture=True, name="Snow_IMAGE#"
            )
            placement = cmds.shadingNode(
                "place2dTexture", asUtility=True, name="Snow_UV#"
            )

            cmds.setAttr(
                texture + ".fileTextureName",
                image_path,
                type="string"
            )
            cmds.setAttr(texture + ".alphaIsLuminance", False)

            cmds.connectAttr(
                placement + ".outUV", texture + ".uvCoord"
            )
            cmds.connectAttr(
                placement + ".outUvFilterSize",
                texture + ".uvFilterSize"
            )
            cmds.connectAttr(
                texture + ".outColor", material + ".color"
            )
            cmds.connectAttr(
                texture + ".outColor",
                material + ".incandescence"
            )
            cmds.connectAttr(
                texture + ".outTransparency",
                material + ".transparency"
            )
            cmds.setAttr(material + ".diffuse", 0)

            resources.extend([texture, placement])

        for index, node in enumerate(resources):
            cmds.connectAttr(
                node + ".message",
                "{}.snowResources[{}]".format(group, index)
            )

        return shading_group

    def create_flake(self, radius, use_image):
        if not use_image:
            return cmds.polySphere(
                name="snowflake#",
                radius=radius,
                subdivisionsX=6,
                subdivisionsY=4,
                constructionHistory=False
            )[0]

        # Two crossed planes display the snowflake image.
        cards = []
        for axis in ((0, 0, 1), (1, 0, 0)):
            card = cmds.polyPlane(
                width=radius * 2,
                height=radius * 2,
                subdivisionsX=1,
                subdivisionsY=1,
                axis=axis,
                constructionHistory=False
            )[0]
            cards.append(card)

        flake = cmds.polyUnite(
            cards,
            constructionHistory=False,
            name="snowflake#"
        )[0]

        for shape in cmds.listRelatives(
            flake, shapes=True, fullPath=True
        ) or []:
            if cmds.attributeQuery("aiOpaque", node=shape, exists=True):
                cmds.setAttr(shape + ".aiOpaque", False)

        return flake

    def generate(self, *_):
        if cmds.upAxis(query=True, axis=True) != "y":
            cmds.warning("This script requires a Y-up scene.")
            return

        image_path = cmds.textFieldButtonGrp(
            self.image_field, query=True, text=True
        ).strip()

        if image_path and not os.path.isfile(image_path):
            cmds.warning("Image not found. Choose an existing PNG.")
            return

        values = {
            key: cmds.floatSliderGrp(
                self.controls[key], query=True, value=True
            )
            for key in ("width", "depth", "height", "size", "wind")
        }

        count = cmds.intSliderGrp(
            self.controls["count"], query=True, value=True
        )
        duration = cmds.intSliderGrp(
            self.controls["duration"], query=True, value=True
        )

        if not 1 <= count <= 1000 or duration < 2:
            cmds.warning(
                "Use 1-1000 flakes and at least 2 frames per fall."
            )
            return

        if any(
            values[key] <= 0
            for key in ("width", "depth", "height", "size")
        ):
            cmds.warning("Dimensions and flake size must be positive.")
            return

        start = cmds.playbackOptions(query=True, minTime=True)
        rng = random.Random()

        cmds.undoInfo(openChunk=True, chunkName="Generate Snow")
        cmds.refresh(suspend=True)

        try:
            self.remove_snow()

            group = cmds.group(empty=True, name="FallingSnow_GRP#")
            cmds.addAttr(
                group,
                longName=self.TAG,
                attributeType="bool",
                defaultValue=True
            )
            cmds.addAttr(
                group,
                longName="snowResources",
                attributeType="message",
                multi=True
            )

            shading_group = self.create_material(group, image_path)

            for _ in range(count):
                radius = values["size"] * rng.uniform(0.6, 1.4)
                flake = self.create_flake(radius, bool(image_path))
                flake = cmds.parent(flake, group)[0]

                cmds.sets(
                    flake, edit=True, forceElement=shading_group
                )

                x = rng.uniform(
                    -values["width"] / 2,
                    values["width"] / 2
                )
                z = rng.uniform(
                    -values["depth"] / 2,
                    values["depth"] / 2
                )

                # Stagger each flake's animation.
                fall_frames = duration * rng.uniform(0.8, 1.2)
                first = start - rng.uniform(0, fall_frames)
                last = first + fall_frames
                drift = values["wind"] * rng.uniform(0.7, 1.3)

                movement = [
                    ("translateX", x, x + drift),
                    ("translateY", values["height"], -radius * 2),
                    ("translateZ", z, z + rng.uniform(-0.5, 0.5)),
                ]

                for attribute, top, bottom in movement:
                    cmds.setKeyframe(
                        flake,
                        attribute=attribute,
                        time=first,
                        value=top
                    )
                    cmds.setKeyframe(
                        flake,
                        attribute=attribute,
                        time=last,
                        value=bottom
                    )
                    cmds.keyTangent(
                        flake,
                        attribute=attribute,
                        inTangentType="linear",
                        outTangentType="linear"
                    )
                    cmds.setInfinity(
                        flake,
                        attribute=attribute,
                        preInfinite="cycle",
                        postInfinite="cycle"
                    )

            cmds.select(group, replace=True)
            cmds.currentTime(start)
            cmds.text(
                self.status,
                edit=True,
                label="{} flakes created. Press 6, then Play!".format(
                    count
                )
            )

        finally:
            cmds.refresh(suspend=False)
            cmds.refresh(force=True)
            cmds.undoInfo(closeChunk=True)

def fix_snow_for_arnold():
    """Apply the supplied Arnold fix after generating image snow."""
    if not cmds.pluginInfo("mtoa", query=True, loaded=True):
        cmds.loadPlugin("mtoa")

    groups = [
        node for node in cmds.ls(type="transform", long=True) or []
        if cmds.attributeQuery("snowResources", node=node, exists=True)
        and any(
            cmds.attributeQuery(tag, node=node, exists=True)
            for tag in ("fallingSnowTool", "studentSnowGeneratorOwned")
        )
    ]

    if not groups:
        cmds.warning("Generate your snow first.")
        return

    cmds.undoInfo(openChunk=True, chunkName="Fix Arnold Snow")
    try:
        for group in groups:
            resources = cmds.listConnections(
                group + ".snowResources", source=True, destination=False
            ) or []
            textures = [node for node in resources if cmds.nodeType(node) == "file"]
            shading_groups = [
                node for node in resources if cmds.nodeType(node) == "shadingEngine"
            ]
            if not textures or not shading_groups:
                cmds.warning("This snow group has no image texture.")
                continue
            texture = textures[0]
            shader = next((node for node in resources
                           if cmds.nodeType(node) == "aiStandardSurface"), None)
            if shader is None:
                shader = cmds.shadingNode(
                    "aiStandardSurface", asShader=True, name="Snow_Arnold_MAT#"
                )
                indices = cmds.getAttr(group + ".snowResources", multiIndices=True) or []
                index = max(indices, default=-1) + 1
                cmds.connectAttr(
                    shader + ".message",
                    "{}.snowResources[{}]".format(group, index)
                )

            # Disconnect any prior color restoration so this button is reusable.
            for plug in [shader + ".emissionColor"] + [
                shader + ".emissionColor" + channel for channel in ("R", "G", "B")
            ]:
                incoming = cmds.connectionInfo(plug, sourceFromDestination=True)
                if incoming:
                    cmds.disconnectAttr(incoming, plug)

            cmds.setAttr(shader + ".base", 0)
            cmds.setAttr(shader + ".specular", 0)
            cmds.setAttr(shader + ".emission", 1)
            cmds.setAttr(shader + ".emissionColor", 1, 1, 1, type="double3")
            cmds.setAttr(texture + ".alphaIsLuminance", False)
            for channel in ("R", "G", "B"):
                cmds.connectAttr(
                    texture + ".outAlpha", shader + ".opacity" + channel, force=True
                )
            for shading_group in shading_groups:
                cmds.connectAttr(
                    shader + ".outColor", shading_group + ".surfaceShader", force=True
                )
            shapes = cmds.listRelatives(
                group, allDescendents=True, type="mesh", fullPath=True
            ) or []
            for shape in shapes:
                if cmds.attributeQuery("aiOpaque", node=shape, exists=True):
                    cmds.setAttr(shape + ".aiOpaque", False)
        print("Arnold snow material updated. Start a fresh render.")
    finally:
        cmds.undoInfo(closeChunk=True)


def restore_snow_colors():
    """Apply the Arnold fix and restore the original PNG colors."""
    cmds.undoInfo(openChunk=True, chunkName="Restore Snow Image Colors")
    try:
        fix_snow_for_arnold()
        for group in cmds.ls(type="transform") or []:
            if not cmds.attributeQuery("snowResources", node=group, exists=True):
                continue
            resources = cmds.listConnections(
                group + ".snowResources", source=True, destination=False
            ) or []
            textures = [node for node in resources if cmds.nodeType(node) == "file"]
            shaders = [node for node in resources
                       if cmds.nodeType(node) == "aiStandardSurface"]
            if textures and shaders:
                for shader in shaders:
                    cmds.connectAttr(
                        textures[0] + ".outColor", shader + ".emissionColor", force=True
                    )
        cmds.refresh(force=True)
        print("Original image colors restored. Restart the Arnold render.")
    finally:
        cmds.undoInfo(closeChunk=True)


snow_generator = SnowGenerator()
