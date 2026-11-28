using System.Collections.Generic;
using UnityEngine;

namespace Zone04
{
    internal sealed class QuarantineMap
    {
        public const float Edge = 46;
        public readonly Transform Root;
        private readonly List<Rect> obstacles = new();
        private QuarantineNavigation regularRoutes, heavyRoutes;
        internal IReadOnlyList<Rect> CoverAreas => obstacles;

        public QuarantineMap(Transform parent, bool generated, int seed)
        {
            Root = Models.Node(parent, "Arena", Vector3.zero);
            var rng = new System.Random(seed);
            string[] grass = { "64865A", "607F7A", "9F8460" };
            string[] roads = { "677C8B", "556984", "706779" };
            int palette = generated ? rng.Next(grass.Length) : 0;
            Models.VisualOnly(Models.Block(Root,"Terrain",new Vector3(0,-.18f,0),92,.35f,92,grass[palette]));
            float[] lanes = { -26,0,26 };
            if (generated)
                for (int i = 0; i < lanes.Length; i++) lanes[i] += rng.Next(-4,5);
            foreach (float lane in lanes)
            {
                Models.VisualOnly(Models.Block(Root,"Road",new Vector3(lane,-.018f,0),5.5f,.04f,92,roads[palette]));
                Models.VisualOnly(Models.Block(Root,"Road",new Vector3(0,-.012f,lane),92,.04f,5.5f,roads[palette]));
                for (int i = -10; i <= 10; i++)
                {
                    if (Mathf.Abs(i*4) < 3) continue;
                    Models.VisualOnly(Models.Block(Root,"Lane mark",new Vector3(lane,.016f,i*4),.105f,.025f,1.8f,"E4C787"));
                    Models.VisualOnly(Models.Block(Root,"Lane mark",new Vector3(i*4,.016f,lane),1.8f,.025f,.105f,"E4C787"));
                }
            }
            for (int i = 0; i < 4; i++)
            {
                var border = Models.Node(Root,"Perimeter",Vector3.zero);
                border.rotation = Quaternion.Euler(0,90*i,0);
                Models.Block(border,"Warning stripe",new Vector3(0,.035f,45.9f),92,.05f,.28f,"E6BD65");
                for (int x = -42; x <= 42; x += 7)
                    Models.Block(border,"Marker",new Vector3(x,.34f,45.8f),.22f,.68f,.22f,"B5AA82");
            }

            if (generated)
            {
                for (int x = -38; x <= 38; x += 9)
                for (int z = -38; z <= 38; z += 9)
                {
                    float px = x+rng.Next(-2,3)*.4f, pz = z+rng.Next(-2,3)*.4f;
                    if (px*px+pz*pz < 95 || rng.NextDouble() < .24) continue;
                    bool roadway = false;
                    foreach (float lane in lanes)
                        roadway |= Mathf.Abs(px-lane)<5.4f || Mathf.Abs(pz-lane)<5.4f;
                    if (!roadway) AddCover(px,pz,rng.Next(6),rng.Next(2)==0);
                }
            }
            else
            {
                AddCover(-11,12,0,false); AddCover(13,10,2,true);
                AddCover(-12,-13,1,true); AddCover(14,-12,3,false);
                AddCover(30,14,4,true); AddCover(-29,-18,3,false);
                AddCover(9,29,5,false); AddCover(-28,24,2,true);
            }
        }

        private void AddCover(float x,float z,int kind,bool rotated)
        {
            float width = kind switch { 1=>5.8f, 3=>4.6f, 4=>4.6f, 5=>3.2f, _=>4.0f };
            float depth = kind switch { 1=>2.05f, 4=>3.2f, 5=>2.6f, _=>2.2f };
            float height = kind switch { 0=>2.24f, 1=>1.93f, 2=>.92f, 4=>2.6f, 5=>2.04f, _=>.65f };
            var root = Models.Node(Root,"Cover",new Vector3(x,0,z));
            root.localRotation = Quaternion.Euler(0,rotated ? 90 : 0,0);
            obstacles.Add(new Rect(x-(rotated?depth:width)/2,z-(rotated?width:depth)/2,
                rotated?depth:width,rotated?width:depth));
            string[] colors = { "437C81", "D5AD60", "A98158", "8DA17C", "68759B", "BB7268" };
            Models.Block(root,"Main body",new Vector3(0,height/2,0),width,height,depth,colors[kind]);
            if (kind==0 || kind==2)
            {
                for (float strip = -width/2+.4f; strip < width/2; strip += .48f)
                    Models.Block(root,"Rib",new Vector3(strip,height*.56f,0),.07f,height*.82f,depth+.018f,"B5C4A9");
            }
            if (kind == 1)
            {
                Models.Block(root,"Roof",new Vector3(0,height+.018f,0),width*.93f,.08f,depth*.95f,"E6C786");
                for (int side=-1; side<=1; side+=2)
                {
                    for (int i=-2; i<=2; i++)
                        Models.Block(root,"Window",new Vector3(i*.93f,1.46f,side*depth/2),.75f,.54f,.04f,"466879");
                    for (int i=-1; i<=1; i+=2)
                        Models.Block(root,"Tire",new Vector3(i*1.75f,.41f,side*(depth/2-.04f)),.63f,.62f,.15f,"333945");
                }
            }
            if (kind==4 || kind==5)
            {
                Models.Block(root,"Roof",new Vector3(0,height,0),width+.16f,.15f,depth+.18f,
                    kind==4?"8996B0":"E3A376");
                Models.Block(root,"Window band",new Vector3(0,height*.65f,depth/2),width*.71f,.38f,.055f,"36596E");
                for(int j=-1;j<=1;j+=2)
                    Models.Block(root,"Roof vent",new Vector3(j*.63f,height+.19f,-.21f),.43f,.27f,.57f,"546A78");
                if(kind==5)
                    for(int j=-3;j<=3;j++)
                        Models.Block(root,"Awning",new Vector3(j*.4f,height*.81f,depth/2+.26f),
                            .39f,.13f,.56f,j%2==0?"F1D2A1":"A95758");
            }
            if (kind == 3)
                for (int i=-2;i<=2;i++)
                    Models.Part(root,"Bush","bush",new Vector3(i*.79f,1.02f,0),
                        new Vector3(.98f,.95f,1.42f),i%2==0?"83A957":"68904C");
        }

        public bool Blocked(Vector2 point, float margin)
        {
            if (Mathf.Abs(point.x)>Edge-margin || Mathf.Abs(point.y)>Edge-margin) return true;
            foreach (Rect r in obstacles)
                if (Expand(r,margin).Contains(point)) return true;
            return false;
        }

        public Vector2 Move(Vector2 start, Vector2 delta, float radius)
        {
            Vector2 target = new(Mathf.Clamp(start.x+delta.x,-Edge+radius,Edge-radius),
                                 Mathf.Clamp(start.y+delta.y,-Edge+radius,Edge-radius));
            Vector2 cursor = start;
            Vector2 xOnly = new(target.x,start.y);
            float hit = FirstCover(cursor,xOnly,radius);
            cursor.x = Mathf.Lerp(cursor.x,xOnly.x,hit<1 ? Mathf.Max(0,hit-.001f) : 1);
            Vector2 yOnly = new(cursor.x,target.y);
            hit = FirstCover(cursor,yOnly,radius);
            cursor.y = Mathf.Lerp(cursor.y,yOnly.y,hit<1 ? Mathf.Max(0,hit-.001f) : 1);
            return cursor;
        }

        public Vector2 Guide(Vector2 start, Vector2 target, float radius)
        {
            if (FirstCover(start,target,radius)>=1) return target;
            QuarantineNavigation routes = radius>.55f
                ? heavyRoutes ??= new QuarantineNavigation(this,.72f)
                : regularRoutes ??= new QuarantineNavigation(this,.53f);
            if (routes.TryGuide(start,target,radius,out Vector2 waypoint))
                return waypoint;
            return Pursuit(start,target,radius);
        }

        public Vector2 Pursuit(Vector2 start,Vector2 target,float radius)
        {
            Rect? nearest=null;
            float first=1;
            foreach (Rect r in obstacles)
            {
                float hit=Entry(Expand(r,radius),start,target);
                if(hit<first) { first=hit; nearest=r; }
            }
            if (!nearest.HasValue) return target;
            Rect expanded=Expand(nearest.Value,radius+.18f);
            Vector2[] corners = {
                new(expanded.xMin,expanded.yMin),new(expanded.xMin,expanded.yMax),
                new(expanded.xMax,expanded.yMin),new(expanded.xMax,expanded.yMax)
            };
            float best=float.PositiveInfinity;
            Vector2 next=target;
            Rect rect=Expand(nearest.Value,radius);
            foreach (Vector2 a in corners)
            {
                if ((start-a).sqrMagnitude<.008f || Entry(rect,start,a)<1) continue;
                foreach (Vector2 b in corners)
                {
                    if (Entry(rect,a,b)<1 || Entry(rect,b,target)<1) continue;
                    float cost=Vector2.Distance(start,a)+Vector2.Distance(a,b)+Vector2.Distance(b,target);
                    if(cost<best){next=a; best=cost;}
                }
            }
            return next;
        }

        public float FirstCover(Vector2 a,Vector2 b,float radius=0)
        {
            float best=1;
            foreach(Rect r in obstacles) best=Mathf.Min(best,Entry(Expand(r,radius),a,b));
            return best;
        }

        private static Rect Expand(Rect r,float m)
        {
            return Rect.MinMaxRect(r.xMin-m,r.yMin-m,r.xMax+m,r.yMax+m);
        }

        private static float Entry(Rect r,Vector2 a,Vector2 b)
        {
            Vector2 d=b-a;
            return CollisionMath.Box(a.x,a.y,d.x,d.y,r.xMin,r.yMin,r.xMax,r.yMax);
        }
    }
}
