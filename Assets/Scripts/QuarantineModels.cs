using System.Collections.Generic;
using UnityEngine;
using UnityEngine.Rendering;

namespace Zone04
{
    internal static class Models
    {
        private static readonly Dictionary<string, Mesh> Meshes = new();
        private static readonly Dictionary<Color32, Material> Materials = new();

        public static Color Tint(string hex)
        {
            ColorUtility.TryParseHtmlString("#" + hex, out Color color);
            return color;
        }

        public static Transform Node(Transform parent, string name, Vector3 position)
        {
            var node = new GameObject(name).transform;
            node.SetParent(parent, false);
            node.localPosition = position;
            return node;
        }

        public static Transform Part(Transform parent, string name, string meshName,
            Vector3 position, Vector3 size, string hex)
        {
            if (!Meshes.TryGetValue(meshName, out Mesh mesh))
            {
                GameObject asset = Resources.Load<GameObject>("Models/" + meshName);
                if (asset == null)
                    throw new System.InvalidOperationException("Missing model: " + meshName);
                mesh = asset.GetComponentInChildren<MeshFilter>().sharedMesh;
                Meshes.Add(meshName, mesh);
            }

            Transform pivot = Node(parent, name, position);
            Transform geometry = Node(pivot, "Mesh", Vector3.zero);
            Vector3 bounds = mesh.bounds.size;
            var scale = new Vector3(size.x/bounds.x, size.y/bounds.y, size.z/bounds.z);
            geometry.localScale = scale;
            geometry.localPosition = -Vector3.Scale(mesh.bounds.center, scale);
            geometry.gameObject.AddComponent<MeshFilter>().sharedMesh = mesh;
            var renderer = geometry.gameObject.AddComponent<MeshRenderer>();
            Color32 color = Tint(hex);
            if (!Materials.TryGetValue(color, out Material material))
            {
                Material template = Resources.Load<Material>("Surface");
                material = template != null
                    ? new Material(template)
                    : new Material(Shader.Find("Standard"));
                material.color = color;
                material.name = "Zone 04 " + hex;
                Materials.Add(color, material);
            }
            renderer.sharedMaterial = material;
            return pivot;
        }

        public static Transform Block(Transform parent, string name, Vector3 position,
            float w, float h, float d, string color)
        {
            return Part(parent, name, "panel", position, new Vector3(w,h,d), color);
        }

        public static void VisualOnly(Transform root)
        {
            foreach (MeshRenderer r in root.GetComponentsInChildren<MeshRenderer>())
            {
                r.shadowCastingMode = ShadowCastingMode.Off;
                r.receiveShadows = false;
            }
        }
    }

    internal sealed class ActorModel
    {
        public readonly Transform Root;
        private readonly Transform hips, torso, head, leftArm, rightArm, leftLeg, rightLeg;
        private Transform weapon;
        private float cycle;
        private readonly bool human;
        private readonly float baseScale;

        public ActorModel(Transform parent, string name, int variant, bool player)
        {
            human = player;
            baseScale = variant == 5 ? 1.45f : variant == 2 || variant == 6 ? 1.17f : variant == 1 ? .89f : 1;
            string[] coats = { "466845", "AB584B", "596A79", "848C44", "855C99", "7F3F48", "C48544" };
            string coat = player ? "327583" : coats[variant];
            string accent = player ? "76E2DF" : variant == 3 ? "BDEA6B" : variant == 4 ? "FF9ADD" : variant == 6 ? "FFD783" : "A7C486";
            string dark = player ? "253D48" : variant == 2 ? "404E5C" : "43413B";
            string skin = player ? "B78D68" : variant == 4 ? "C896BB" : "A4B67A";

            Root = Models.Node(parent, name, Vector3.zero);
            Root.localScale = Vector3.one * baseScale;
            hips = Models.Node(Root, "Pelvis", new Vector3(0,.86f,0));
            Models.Part(hips,"Belt","torso",Vector3.zero,new Vector3(.53f,.27f,.35f),dark);
            torso = Models.Node(hips,"Spine",new Vector3(0,.07f,0));
            Models.Part(torso,"Jacket","torso",new Vector3(0,.35f,0),new Vector3(.66f,.66f,.38f),coat);
            Models.Block(torso,"Chest straps",new Vector3(0,.39f,.194f),.49f,.29f,.075f,dark);
            Models.Block(torso,"Chest patch",new Vector3(-.15f,.45f,.24f),.12f,.085f,.025f,accent);
            if (player || variant == 2 || variant == 5)
            {
                Models.Block(torso,"Pack",new Vector3(0,.35f,-.25f),.45f,.51f,.235f,dark);
                Models.Block(torso,"Pack marking",new Vector3(0,.44f,-.375f),.25f,.08f,.025f,accent);
                for (int i = -1; i <= 1; i++)
                    Models.Block(torso,"Pouch",new Vector3(i*.13f,.22f,.235f),.09f,.14f,.065f,coat);
            }
            head = Models.Node(torso,"Neck",new Vector3(0,.70f,0));
            Models.Part(head,"Face","head",new Vector3(0,.14f,.005f),new Vector3(.32f,.37f,.31f),skin);
            if (player || variant == 2)
            {
                Models.Part(head,"Helmet","helmet",new Vector3(0,.235f,-.025f),new Vector3(.39f,.26f,.37f),dark);
                Models.Block(head,"Visor",new Vector3(0,.205f,.163f),.30f,.085f,.039f,accent);
                Models.Block(head,"Radio",new Vector3(-.226f,.29f,-.09f),.032f,.24f,.032f,dark);
            }
            else
            {
                Models.Block(head,"Jaw",new Vector3(0,.066f,.149f),.18f,.075f,.075f,"694E4E");
                for (int side = -1; side <= 1; side += 2)
                    Models.Block(head,"Eye",new Vector3(side*.068f,.17f,.158f),.05f,.036f,.044f,accent);
                if (variant == 6)
                    for(int side=-1; side<=1; side+=2)
                        Models.Block(head,"Head plate",new Vector3(side*.15f,.22f,.09f),.12f,.19f,.27f,accent);
                if (variant == 3 || variant == 4)
                    Models.Part(torso, "Growth", "bush", new Vector3(.07f,.43f,-.20f),
                        new Vector3(.36f,.52f,.29f),accent);
            }

            leftArm = Arm(-1, coat, dark, skin, accent);
            rightArm = Arm(1, coat, dark, skin, accent);
            leftLeg = Leg(-1, dark, coat);
            rightLeg = Leg(1, dark, coat);
        }

        private Transform Arm(int side, string coat, string dark, string skin, string accent)
        {
            Transform arm = Models.Node(torso,"Shoulder",new Vector3(side*.34f,.54f,0));
            Models.Part(arm,"Upper arm","limb",new Vector3(0,-.17f,0),new Vector3(.23f,.43f,.25f),coat);
            Models.Block(arm,"Shoulder plate",new Vector3(side*.043f,-.06f,0),.22f,.18f,.28f,
                human ? accent : coat);
            Transform elbow = Models.Node(arm,"Elbow",new Vector3(0,-.36f,0));
            elbow.localRotation = Quaternion.Euler(human ? -32 : -12,0,0);
            Models.Part(elbow,"Forearm","limb",new Vector3(0,-.14f,0),new Vector3(.16f,.29f,.19f),dark);
            Models.Part(elbow,"Hand","head",new Vector3(0,-.305f,.02f),new Vector3(.15f,.18f,.16f),skin);
            return arm;
        }

        private Transform Leg(int side, string dark, string coat)
        {
            Transform leg = Models.Node(hips,"Hip",new Vector3(side*.15f,-.067f,0));
            Models.Part(leg,"Trousers","limb",new Vector3(0,-.21f,0),new Vector3(.244f,.45f,.26f),dark);
            Transform knee = Models.Node(leg,"Knee",new Vector3(0,-.38f,0));
            Models.Part(knee,"Greave","limb",new Vector3(0,-.14f,0),new Vector3(.18f,.36f,.18f),coat);
            Models.Block(knee,"Boot",new Vector3(0,-.32f,.062f),.22f,.18f,.36f,"253138");
            return leg;
        }

        public void Equip(int index)
        {
            if (weapon != null)
            {
                weapon.gameObject.SetActive(false);
                Object.Destroy(weapon.gameObject);
            }
            weapon = Models.Node(torso,"Weapon",new Vector3(.22f,.29f,.49f));
            BuildWeapon(weapon,index);
        }

        public static void BuildWeapon(Transform weapon,int index)
        {
            float[] lengths={.85f,1.04f,.66f,1.14f,1.08f,1.32f};
            float length=lengths[index];
            string[] finishes = { "5C8890", "BD7B4B", "7D9B9D", "7F9C5D", "9A8A55", "6675AA" };
            Models.Block(weapon,"Receiver",Vector3.zero,.15f,.17f,length*.61f,finishes[index]);
            Models.Block(weapon,"Stock",new Vector3(0,-.026f,-length*.41f),.15f,.20f,length*.25f,"273A44");
            Models.Block(weapon,"Magazine",new Vector3(0,-.14f,.01f),.10f,.18f,.17f,"353942");
            Transform muzzle = Models.Part(weapon,"Barrel","barrel", new Vector3(0,.023f,length*.41f),
                new Vector3(.077f,length*.38f,.077f),"374B56");
            muzzle.localRotation = Quaternion.Euler(90,0,0);
            if (index == 4)
                Models.Block(weapon,"Belt box",new Vector3(.085f,-.105f,.02f),.22f,.23f,.25f,"886747");
            if (index == 3 || index == 5)
                Models.Block(weapon,"Scope",new Vector3(0,.12f,.035f),.075f,.083f,.21f,"B3C3BD");
        }

        public void Collapse(float yaw,float fraction)
        {
            float t=Mathf.Clamp01(fraction);
            Root.rotation=Quaternion.Euler(0,yaw,Mathf.SmoothStep(0,79,t));
            hips.localPosition=new Vector3(0,Mathf.SmoothStep(.86f,.31f,t),0);
        }

        public void Animate(float dt, float move, float bodyYaw, float aimYaw,
            float dash, float attack, float recoil, float reload)
        {
            cycle += dt * (human ? 10.5f : 8f) * Mathf.Lerp(.4f,1.45f,move);
            float swing = Mathf.Sin(cycle)*move;
            Root.rotation = Quaternion.Euler(0,bodyYaw,0);
            hips.localPosition = new Vector3(0,.86f + Mathf.Abs(swing)*.066f - dash*.23f,0);
            torso.localRotation = Quaternion.Euler(dash*36 + attack*26 - recoil*7,
                human ? Mathf.DeltaAngle(bodyYaw,aimYaw) : 0, swing*4);
            head.localRotation = Quaternion.Euler(-dash*20-attack*12,0,0);
            leftLeg.localRotation = Quaternion.Euler(swing*35 + dash*33,0,-3);
            rightLeg.localRotation = Quaternion.Euler(-swing*35-dash*38,0,3);
            leftLeg.GetChild(1).localRotation = Quaternion.Euler(Mathf.Max(0,-swing)*29+dash*18,0,0);
            rightLeg.GetChild(1).localRotation = Quaternion.Euler(Mathf.Max(0,swing)*29+dash*26,0,0);
            float guard = human ? -61 : -29;
            leftArm.localRotation = Quaternion.Euler(guard-swing*13-attack*49+reload*50,0,-13);
            rightArm.localRotation = Quaternion.Euler(guard+swing*13-attack*59+reload*29,0,13);
            if (weapon != null)
                weapon.localRotation = Quaternion.Euler(-recoil*11+reload*51,0,-reload*32);
        }
    }
}
