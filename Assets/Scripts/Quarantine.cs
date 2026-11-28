using System.Collections.Generic;
using UnityEngine;

namespace Zone04
{
    public sealed class Quarantine : MonoBehaviour
    {
        private enum ScreenState { Title, Playing, Pause, Upgrade, Defeat }
        private enum EnemyKind { Walker, Runner, Armored, Spitter, Caller, Boss }

        private sealed class Enemy
        {
            public EnemyKind Kind;
            public ActorModel Model;
            public Vector2 Position, Direction, Aim;
            public float Hp, MaxHp, Armor, Speed, Radius, Windup, Cooldown, Swing, Stuck;
            public bool Called;
        }

        private sealed class Projectile
        {
            public Transform Model;
            public Vector2 Position, Velocity;
            public float Life, Damage;
            public bool Acid;
        }

        private sealed class Supply
        {
            public Transform Model;
            public Vector2 Position;
            public int Ammo, Weapon;
            public float Heal;
        }

        private readonly struct Weapon
        {
            public readonly string Name;
            public readonly int Capacity, Pellets;
            public readonly float Damage, Delay, Reload, Speed, Reach;
            public Weapon(string name,int capacity,int pellets,float damage,float delay,float reload,float speed,float reach)
            {
                Name=name; Capacity=capacity; Pellets=pellets; Damage=damage; Delay=delay;
                Reload=reload; Speed=speed; Reach=reach;
            }
        }

        private static readonly Weapon[] Weapons =
        {
            new("Карабин",18,1,26,.24f,1.1f,46,30),
            new("Дробовик",7,6,11,.62f,1.6f,37,14),
            new("Пистолет-пулемёт",30,1,15,.12f,1.3f,41,23),
            new("Винтовка",8,1,61,.64f,1.4f,57,37)
        };
        private static readonly string[] Upgrades =
        {
            "Усиленные патроны", "Лёгкое снаряжение", "Аптечка", "Запас патронов",
            "Бронежилет", "Быстрые руки", "Быстрый рывок", "Длинные магазины"
        };
        private static readonly string[] UpgradeDetails =
        {
            "+25% урона", "+12% к скорости бега", "+35 здоровья", "+55 патронов",
            "−15% получаемого урона", "−20% времени перезарядки", "−20% отката рывка", "+4 патрона в магазине"
        };

        private Camera view;
        private AudioSource audioPlayer;
        private readonly Dictionary<string,AudioClip> audioClips=new();
        private float volume;
        private Transform arenaContents;
        private QuarantineMap map;
        private ActorModel player;
        private readonly List<Enemy> enemies=new();
        private readonly List<Projectile> shots=new();
        private readonly List<Supply> supplies=new();
        private readonly List<int> choices=new();
        private ScreenState state;
        private bool generated;
        private int difficulty=1, wave, remaining, kills, xp, level, best, weaponId, magazine, ammo, bonusMagazine;
        private float hp, spawnTimer, rest, shotTimer, reloadTimer, elapsed, dashReady, dashTime;
        private float damage, speed, armor, reloadMultiplier, dashCooldown, bodyYaw, aimYaw, recoil;
        private Vector2 position, dashStart, dashDirection, aim=Vector2.up;
        private float dashLength;
        private bool showMap=true;
        private string notice="";
        private float noticeUntil;
        private GUIStyle headline, text, small, button;
        private Texture2D white;
        private static readonly Color Ink=Models.Tint("182B43");
        private static readonly Color Mint=Models.Tint("83E8DD");
        private static readonly Color Gold=Models.Tint("F8D484");
        private static readonly Color Pale=Models.Tint("E8F1F3");

        [RuntimeInitializeOnLoadMethod(RuntimeInitializeLoadType.AfterSceneLoad)]
        private static void Boot()
        {
            if (FindObjectOfType<Quarantine>() == null)
                new GameObject("Zone 04").AddComponent<Quarantine>();
        }

        private void Start()
        {
            Application.targetFrameRate=120;
            QualitySettings.shadowDistance=45;
            best=PlayerPrefs.GetInt("Zone04.Best");
            difficulty=Mathf.Clamp(PlayerPrefs.GetInt("Zone04.Difficulty",1),0,2);
            showMap=PlayerPrefs.GetInt("Zone04.Map",1)==1;
            volume=Mathf.Clamp01(PlayerPrefs.GetFloat("Zone04.Volume",.6f));
            if (PlayerPrefs.HasKey("Zone04.Fullscreen"))
                Screen.fullScreenMode=PlayerPrefs.GetInt("Zone04.Fullscreen")==1
                    ? FullScreenMode.FullScreenWindow : FullScreenMode.Windowed;

            view=new GameObject("Tactical camera").AddComponent<Camera>();
            view.clearFlags=CameraClearFlags.SolidColor;
            view.backgroundColor=Models.Tint("2A4050");
            view.orthographic=true;
            view.gameObject.AddComponent<AudioListener>();
            audioPlayer=view.gameObject.AddComponent<AudioSource>();
            view.nearClipPlane=.15f;
            view.farClipPlane=125;
            view.gameObject.tag="MainCamera";
            view.transform.rotation=Quaternion.Euler(59,0,0);
            var light=new GameObject("Sun").AddComponent<Light>();
            light.type=LightType.Directional;
            light.intensity=1.28f;
            light.color=Models.Tint("FFF1D3");
            light.shadows=LightShadows.Soft;
            light.transform.rotation=Quaternion.Euler(47,-38,0);
            RenderSettings.ambientLight=Models.Tint("A2ADB9");
            StartMatch(true);
            Spawn(EnemyKind.Walker,new Vector2(3,-1));
            Spawn(EnemyKind.Armored,new Vector2(7,1));
            Spawn(EnemyKind.Runner,new Vector2(5,-4));
            state=ScreenState.Title;
            FocusCamera(position-Vector2.right*4,true);
        }

        private void Sound(string name,float gain=1)
        {
            if(volume<=0) return;
            if(!audioClips.TryGetValue(name,out AudioClip clip))
            {
                clip=Resources.Load<AudioClip>("Sounds/"+name);
                audioClips.Add(name,clip);
            }
            if(clip!=null) audioPlayer.PlayOneShot(clip,volume*gain);
        }

        private void StartMatch(bool randomMap)
        {
            if (arenaContents!=null)
            {
                arenaContents.gameObject.SetActive(false);
                Destroy(arenaContents.gameObject);
            }
            arenaContents=Models.Node(null,"Match",Vector3.zero);
            map=new QuarantineMap(arenaContents,randomMap,Random.Range(1,int.MaxValue));
            player=new ActorModel(arenaContents,"Scout",0,true);
            player.Equip(0);
            generated=randomMap;
            enemies.Clear(); shots.Clear(); supplies.Clear();
            wave=remaining=kills=xp=bonusMagazine=weaponId=0;
            level=1; hp=100; magazine=18; ammo=98;
            rest=3; spawnTimer=shotTimer=reloadTimer=elapsed=dashReady=dashTime=0;
            damage=speed=armor=reloadMultiplier=1;
            dashCooldown=2.4f;
            position=Vector2.zero;
            bodyYaw=aimYaw=0;
            aim=Vector2.up;
            recoil=0;
            notice=""; noticeUntil=0;
            state=ScreenState.Playing;
            FocusCamera(position,true);
        }

        private void Update()
        {
            if (Input.GetKeyDown(KeyCode.F11) ||
                (Input.GetKeyDown(KeyCode.Return)&&(Input.GetKey(KeyCode.LeftAlt)||Input.GetKey(KeyCode.RightAlt))))
                SetDisplay(Screen.fullScreenMode==FullScreenMode.Windowed);
            else if (state==ScreenState.Title)
            {
                if (Input.GetKeyDown(KeyCode.Alpha1)) StartMatch(false);
                if (Input.GetKeyDown(KeyCode.Alpha2)) StartMatch(true);
            }
            else if (state==ScreenState.Pause && Input.GetKeyDown(KeyCode.Escape))
                state=ScreenState.Playing;
            else if (state==ScreenState.Upgrade)
            {
                for (int i=0;i<3;i++)
                    if (Input.GetKeyDown((KeyCode)((int)KeyCode.Alpha1+i))) Choose(i);
            }
            else if (state==ScreenState.Defeat && Input.GetKeyDown(KeyCode.Return))
                StartMatch(generated);
            else if (state==ScreenState.Playing)
            {
                if (Input.GetKeyDown(KeyCode.Escape))
                    state=ScreenState.Pause;
                else
                    Tick(Mathf.Min(.05f,Time.deltaTime));
            }

            Cursor.visible=state!=ScreenState.Playing;
            view.orthographicSize=state==ScreenState.Title ? 11 : 14;
        }

        private void OnApplicationFocus(bool focused)
        {
            if (!focused && state==ScreenState.Playing) state=ScreenState.Pause;
        }

        private static float Yaw(Vector2 vector)
        {
            return Mathf.Atan2(vector.x,vector.y)*Mathf.Rad2Deg;
        }

        private static Vector3 World(Vector2 p,float height=0) => new(p.x,height,p.y);

        private void FocusCamera(Vector2 p,bool immediate=false)
        {
            Vector3 target=World(p)+new Vector3(0,24,-14.4f);
            view.transform.position=immediate?target:
                Vector3.Lerp(view.transform.position,target,1-Mathf.Exp(-14*Time.deltaTime));
        }

        private void Tick(float dt)
        {
            elapsed+=dt;
            Vector2 key=new(
                (Input.GetKey(KeyCode.D)||Input.GetKey(KeyCode.RightArrow)?1:0)-
                (Input.GetKey(KeyCode.A)||Input.GetKey(KeyCode.LeftArrow)?1:0),
                (Input.GetKey(KeyCode.W)||Input.GetKey(KeyCode.UpArrow)?1:0)-
                (Input.GetKey(KeyCode.S)||Input.GetKey(KeyCode.DownArrow)?1:0));
            key=key.normalized;
            Ray ray=view.ScreenPointToRay(Input.mousePosition);
            if (new Plane(Vector3.up,Vector3.zero).Raycast(ray,out float hit))
            {
                Vector3 cursor=ray.GetPoint(hit);
                Vector2 delta=new Vector2(cursor.x,cursor.z)-position;
                if (delta.sqrMagnitude>.02f) aim=delta.normalized;
            }
            aimYaw=Yaw(aim);
            if (Input.GetKeyDown(KeyCode.Space) && elapsed>=dashReady)
                Dash(key.sqrMagnitude>0?key:aim);
            float dashPose=0;
            bool dashing=dashTime>0;
            Vector2 previous=position;
            if (dashing)
            {
                dashTime=Mathf.Max(0,dashTime-dt);
                float t=1-dashTime/.22f;
                position=dashStart+dashDirection*dashLength*(t*t*(3-2*t));
                dashPose=Mathf.Sin(Mathf.PI*t);
                bodyYaw=Yaw(dashDirection);
                aimYaw=bodyYaw;
            }
            else
            {
                position=map.Move(position,key*6.4f*speed*dt,.37f);
                float desired=key.sqrMagnitude>0 ? Yaw(key) : aimYaw;
                bodyYaw=Mathf.MoveTowardsAngle(bodyYaw,desired,720*dt);
            }
            player.Root.position=World(position);
            shotTimer=Mathf.Max(0,shotTimer-dt);
            recoil=Mathf.Max(0,recoil-dt*7);
            if (reloadTimer>0)
            {
                reloadTimer-=dt;
                if (reloadTimer<=0)
                {
                    int amount=Mathf.Min(ammo,Weapons[weaponId].Capacity+bonusMagazine-magazine);
                    magazine+=amount; ammo-=amount;
                }
            }
            if (Input.GetKeyDown(KeyCode.R)) Reload();
            if (Input.GetMouseButton(0) && !dashing && reloadTimer<=0 && shotTimer<=0)
                TryFire();
            if (Input.GetKeyDown(KeyCode.E)) Collect(false);
            if (Input.GetKeyDown(KeyCode.F)) Collect(true);
            float reloadPose=reloadTimer>0 ? Mathf.Sin(Mathf.PI*reloadTimer/(Weapons[weaponId].Reload*reloadMultiplier)) : 0;
            player.Animate(dt,Mathf.Clamp01((position-previous).magnitude/(dt*6.4f+.001f)),bodyYaw,aimYaw,dashPose,0,recoil,reloadPose);
            FocusCamera(position);
            UpdateWave(dt);
            UpdateShots(dt);
            if (state!=ScreenState.Playing) return;
            UpdateEnemies(dt);
            if (state==ScreenState.Playing && xp>=XpGoal) OfferUpgrade();
        }

        private void Dash(Vector2 direction)
        {
            float length=3.7f;
            if (Mathf.Abs(direction.x)>.001f)
                length=Mathf.Min(length,((direction.x>0?45.63f:-45.63f)-position.x)/direction.x);
            if (Mathf.Abs(direction.y)>.001f)
                length=Mathf.Min(length,((direction.y>0?45.63f:-45.63f)-position.y)/direction.y);
            length*=map.FirstCover(position,position+direction*length,.37f);
            if (length<=.06f) return;
            dashStart=position; dashDirection=direction; dashLength=length-.025f;
            dashTime=.22f; dashReady=elapsed+dashCooldown;
            Sound("dash");
        }

        private void Reload()
        {
            Weapon w=Weapons[weaponId];
            if (reloadTimer<=0 && ammo>0 && magazine<w.Capacity+bonusMagazine)
            {
                reloadTimer=w.Reload*reloadMultiplier;
                Sound("reload");
            }
        }

        private void TryFire()
        {
            if (magazine==0) { Reload(); return; }
            Weapon w=Weapons[weaponId];
            magazine--;
            Sound("shot",.8f);
            shotTimer=w.Delay;
            recoil=1;
            for (int i=0;i<w.Pellets;i++)
            {
                float spread=w.Pellets==1 ? 0 : (i-(w.Pellets-1)*.5f)*.075f;
                Vector2 direction=new(aim.x*Mathf.Cos(spread)+aim.y*Mathf.Sin(spread),
                    aim.y*Mathf.Cos(spread)-aim.x*Mathf.Sin(spread));
                AddProjectile(position,direction,w.Speed,w.Reach,w.Damage*damage,false);
            }
        }

        private void AddProjectile(Vector2 start,Vector2 direction,float speedValue,float range,float power,bool acid)
        {
            Transform model=Models.Block(arenaContents,acid?"Acid":"Projectile",World(start,.82f),
                acid?.22f:.072f,acid?.18f:.072f,acid?.24f:.26f,acid?"BAFF72":"FFE6A1");
            Models.VisualOnly(model);
            model.rotation=Quaternion.Euler(0,Yaw(direction),0);
            shots.Add(new Projectile { Model=model, Position=start, Velocity=direction*speedValue,
                Life=range/speedValue, Damage=power, Acid=acid });
        }

        private static float CircleHit(Vector2 a,Vector2 delta,Vector2 center,float radius)
        {
            Vector2 f=a-center;
            return CollisionMath.Circle(f.x,f.y,delta.x,delta.y,radius);
        }

        private void UpdateShots(float dt)
        {
            for(int i=shots.Count-1;i>=0;i--)
            {
                Projectile shot=shots[i];
                float travel=Mathf.Min(dt,shot.Life);
                Vector2 delta=shot.Velocity*travel;
                Vector2 end=shot.Position+delta;
                float stop=map.FirstCover(shot.Position,end);
                if(shot.Acid)
                {
                    if(CircleHit(shot.Position,delta,position,.46f)<stop)
                    {
                        Hurt(shot.Damage);
                        stop=0;
                    }
                }
                else
                {
                    Enemy target=null;
                    foreach(Enemy enemy in enemies)
                    {
                        float hit=CircleHit(shot.Position,delta,enemy.Position,enemy.Radius);
                        if(hit<stop) { stop=hit; target=enemy; }
                    }
                    if(target!=null)
                    {
                        float blocked=Mathf.Min(target.Armor,shot.Damage*.65f);
                        target.Armor-=blocked;
                        target.Hp-=shot.Damage-blocked;
                        if(target.Hp<=0) Kill(target);
                    }
                }
                shot.Life-=travel;
                if(stop<1 || shot.Life<=0 || map.Blocked(end,0))
                {
                    Destroy(shot.Model.gameObject);
                    shots.RemoveAt(i);
                }
                else
                {
                    shot.Position=end;
                    shot.Model.position=World(end,.82f);
                }
                if(state==ScreenState.Defeat) return;
            }
        }

        private void UpdateWave(float dt)
        {
            if(remaining>0)
            {
                spawnTimer-=dt;
                if(spawnTimer>0) return;
                float roll=Random.value;
                EnemyKind kind=wave%5==0 && remaining==1 ? EnemyKind.Boss
                    : wave>=6 && roll<.14f ? EnemyKind.Caller
                    : wave>=4 && roll<.28f ? EnemyKind.Spitter
                    : wave>=2 && roll<.47f ? EnemyKind.Armored
                    : wave>=2 && roll<.73f ? EnemyKind.Runner : EnemyKind.Walker;
                if(!FindSpawn(out Vector2 point)) {spawnTimer=.12f;return;}
                Spawn(kind,point);
                remaining--;
                spawnTimer=Mathf.Max(.16f,.69f-wave*.034f)*(1.18f-.2f*difficulty);
            }
            else if(enemies.Count==0)
            {
                rest-=dt;
                if(rest>0) return;
                wave++;
                Sound("wave");
                remaining=Mathf.Min(70,Mathf.RoundToInt((8+wave*5)*(.78f+.24f*difficulty)));
                rest=5-difficulty;
                spawnTimer=0;
                if(wave>1 && FindSupply(out Vector2 point))
                    Drop(point,wave%2==0?1+(wave/2-1)%3:-1,38,16);
                Announce(wave%5==0 ? "Волна "+wave+" — громила" : "Волна "+wave);
            }
        }

        private bool FindSpawn(out Vector2 point)
        {
            for(int i=0;i<64;i++)
            {
                float angle=Random.Range(0f,Mathf.PI*2);
                float radius=Random.Range(20f,34f);
                Vector2 candidate=position+new Vector2(Mathf.Sin(angle),Mathf.Cos(angle))*radius;
                if(map.Blocked(candidate,1.3f)) continue;
                Vector3 projected=view.WorldToViewportPoint(World(candidate));
                if(projected.x>-.03f && projected.x<1.03f && projected.y>-.03f && projected.y<1.03f) continue;
                point=candidate;
                return true;
            }
            // Narrow corridors and very wide displays can reject most random points.
            float best=-1;
            point=Vector2.zero;
            foreach(int x in new[]{-1,1})
            foreach(int z in new[]{-1,1})
            {
                Vector2 corner=new(x*44,z*44);
                Vector3 projected=view.WorldToViewportPoint(World(corner));
                if (projected.x>-.03f && projected.x<1.03f && projected.y>-.03f && projected.y<1.03f)
                    continue;
                float distance=(corner-position).sqrMagnitude;
                if(!map.Blocked(corner,1.3f)&&distance>best) {point=corner;best=distance;}
            }
            return best>=0;
        }

        private bool FindSupply(out Vector2 point)
        {
            for(int i=0;i<16;i++)
            {
                float angle=Random.value*Mathf.PI*2;
                point=position+new Vector2(Mathf.Sin(angle),Mathf.Cos(angle))*3.5f;
                if(!map.Blocked(point,.4f) && map.FirstCover(position,point,.35f)>=1) return true;
            }
            point=position;
            return true;
        }

        private void Spawn(EnemyKind kind,Vector2 point)
        {
            int variant=(int)kind;
            float[] health={1,.62f,1.55f,.84f,1.02f,6.7f};
            float[] velocity={2.6f,4.9f,2.05f,2.62f,2.54f,3.36f};
            float[] radii={.40f,.35f,.49f,.41f,.42f,.69f};
            var e=new Enemy { Kind=kind, Position=point, Direction=Vector2.up,
                Hp=(33+wave*5)*(.88f+difficulty*.24f)*health[variant],
                Speed=velocity[variant]*(.93f+.115f*difficulty),Radius=radii[variant] };
            e.MaxHp=e.Hp;
            e.Armor=kind==EnemyKind.Armored?e.Hp*.45f:0;
            e.Model=new ActorModel(arenaContents,kind.ToString(),variant,false);
            e.Model.Root.position=World(point);
            enemies.Add(e);
        }

        private void UpdateEnemies(float dt)
        {
            var reinforcements=new List<Vector2>();
            for(int i=0;i<enemies.Count;i++)
            {
                Enemy e=enemies[i];
                Vector2 toPlayer=position-e.Position;
                float gap=toPlayer.magnitude;
                bool clear=map.FirstCover(e.Position,position)>=1;
                float reach=e.Kind==EnemyKind.Boss?2.2f:1.08f;
                bool ranged=e.Kind==EnemyKind.Spitter;
                bool canCall=e.Kind==EnemyKind.Caller && !e.Called && enemies.Count<66;
                e.Cooldown=Mathf.Max(0,e.Cooldown-dt);
                e.Swing=Mathf.Max(0,e.Swing-dt*5f);
                Vector2 previous=e.Position;
                if(e.Windup>0)
                {
                    e.Windup-=dt;
                    if(e.Windup<=0)
                    {
                        e.Swing=1;
                        e.Cooldown=ranged?2.4f:e.Kind==EnemyKind.Boss?1.35f:.82f;
                        if(ranged)
                        {
                            AddProjectile(e.Position,e.Aim,11.8f,13,14,true);
                            Sound("spit",.7f);
                        }
                        else if(canCall)
                        {
                            e.Called=true;
                            Sound("call",.7f);
                            Vector2 side=new(e.Aim.y,-e.Aim.x);
                            foreach(int sign in new[]{-1,1})
                            {
                                Vector2 at=e.Position+side*1.35f*sign;
                                if(!map.Blocked(at,.4f) && Vector2.Distance(position,at)>1.1f)
                                    reinforcements.Add(at);
                            }
                        }
                        else if(gap<=reach && clear)
                            Hurt(e.Kind==EnemyKind.Boss?28:e.Kind==EnemyKind.Armored?16:10);
                    }
                }
                else if(e.Cooldown<=0 && clear && gap<=(ranged?10:canCall?8:reach))
                {
                    e.Windup=ranged?.58f:canCall?.72f:e.Kind==EnemyKind.Boss?.68f:.29f;
                    e.Aim=toPlayer.normalized;
                    if(e.Aim.sqrMagnitude<.01f) e.Aim=e.Direction;
                    e.Direction=e.Aim;
                }
                else if(!clear || gap>(ranged?6.6f:reach*.8f))
                {
                    Vector2 point=map.Pursuit(e.Position,position,e.Radius);
                    Vector2 direction=(point-e.Position).normalized;
                    if((point-position).sqrMagnitude<.01f)
                    {
                        foreach(Enemy other in enemies)
                        {
                            Vector2 away=e.Position-other.Position;
                            float separation=e.Radius+other.Radius;
                            if(away.sqrMagnitude>0 && away.sqrMagnitude<separation*separation*.7f)
                                direction+=away*1.35f;
                        }
                    }
                    e.Position=map.Move(e.Position,direction.normalized*e.Speed*dt,e.Radius);
                    if((e.Position-previous).sqrMagnitude>.00001f) e.Direction=direction.normalized;
                    e.Stuck=(e.Position-previous).sqrMagnitude<.000001f?e.Stuck+dt:0;
                    if(e.Stuck>1.5f && FindSpawn(out Vector2 openPosition))
                    {
                        e.Position=openPosition;
                        e.Stuck=0;
                    }
                }
                e.Model.Root.position=World(e.Position);
                e.Model.Animate(dt,Mathf.Clamp01((e.Position-previous).magnitude/(dt*e.Speed+.001f)),
                    Yaw(e.Direction),0,0,e.Windup>0?-.31f:e.Swing,0,0);
                if(state==ScreenState.Defeat) return;
            }
            foreach(Vector2 p in reinforcements) Spawn(EnemyKind.Runner,p);
        }

        private void Kill(Enemy e)
        {
            enemies.Remove(e);
            Destroy(e.Model.Root.gameObject);
            kills++;
            xp+=e.Kind==EnemyKind.Boss?5:1;
            if(e.Kind==EnemyKind.Boss || kills%3==0)
                Drop(e.Position,-1,e.Kind==EnemyKind.Boss?62:12,e.Kind==EnemyKind.Boss?24:0);
        }

        private void Hurt(float amount)
        {
            Sound("hit");
            hp=Mathf.Max(0,hp-amount*(.78f+.28f*difficulty)*armor);
            if(hp>0) return;
            state=ScreenState.Defeat;
            player.Animate(0,0,bodyYaw,aimYaw,0,0,0,0,true);
            if(kills<=best) return;
            best=kills;
            PlayerPrefs.SetInt("Zone04.Best",best);
            PlayerPrefs.Save();
        }

        private void Drop(Vector2 p,int weapon,int rounds,float heal)
        {
            Transform model=Models.Block(arenaContents,weapon>=0?"Weapon cache":"Supplies",World(p,.25f),
                .78f,.49f,.63f,weapon>=0?"DDBB60":heal>0?"82C681":"AF9263");
            Models.Block(model,"Lid band",new Vector3(0,.24f,0),.14f,.025f,.61f,"E4EAD4");
            supplies.Add(new Supply { Model=model, Position=p, Ammo=rounds, Weapon=weapon, Heal=heal });
        }

        private Supply Nearby(bool weapon)
        {
            float nearest=2;
            Supply result=null;
            foreach(Supply s in supplies)
            {
                if(weapon ? s.Weapon<0 : s.Ammo==0 && s.Heal==0) continue;
                float gap=Vector2.Distance(position,s.Position);
                if(gap>=nearest || map.FirstCover(position,s.Position)<1) continue;
                nearest=gap; result=s;
            }
            return result;
        }

        private void Collect(bool equip)
        {
            Supply s=Nearby(equip);
            if(s==null) return;
            Sound("pickup");
            int collected = s.Ammo;
            ammo+=collected;
            hp=Mathf.Min(100,hp+s.Heal);
            s.Ammo=0;
            s.Heal=0;
            if(equip)
            {
                int previous=weaponId;
                weaponId=s.Weapon;
                s.Weapon=previous;
                s.Ammo=magazine;
                magazine=0;
                reloadTimer=0;
                player.Equip(weaponId);
                Reload();
                Announce(Weapons[weaponId].Name);
            }
            else if(collected>0)
                Announce("Припасы · +"+collected+" патронов");
            else
                Announce("Здоровье восстановлено");
            if(s.Weapon>=0) return;
            Destroy(s.Model.gameObject);
            supplies.Remove(s);
        }

        private int XpGoal => 5+3*(level-1);

        private void OfferUpgrade()
        {
            xp-=XpGoal;
            level++;
            choices.Clear();
            while(choices.Count<3)
            {
                int next=Random.Range(0,Upgrades.Length);
                if(!choices.Contains(next)) choices.Add(next);
            }
            state=ScreenState.Upgrade;
        }

        private void Choose(int i)
        {
            switch(choices[i])
            {
                case 0: damage+=.25f; break;
                case 1: speed+=.12f; break;
                case 2: hp=Mathf.Min(100,hp+35); break;
                case 3: ammo+=55; break;
                case 4: armor*=.85f; break;
                case 5: reloadMultiplier*=.8f; break;
                case 6: dashCooldown*=.8f; break;
                case 7: bonusMagazine+=4; break;
            }
            state=ScreenState.Playing;
        }

        private void Announce(string line) { notice=line; noticeUntil=elapsed+2.6f; }

        private void SetDisplay(bool full)
        {
            Screen.fullScreenMode=full ? FullScreenMode.FullScreenWindow : FullScreenMode.Windowed;
            PlayerPrefs.SetInt("Zone04.Fullscreen",full?1:0);
            PlayerPrefs.Save();
        }

        private void Skin()
        {
            if (white!=null) return;
            white=Texture2D.whiteTexture;
            headline=LabelStyle(54,FontStyle.Bold,Pale);
            text=LabelStyle(20,FontStyle.Bold,Pale);
            small=LabelStyle(15,FontStyle.Normal,Models.Tint("B8CAD7"));
            button=new GUIStyle(GUI.skin.button) { fontSize=17, fontStyle=FontStyle.Bold,
                alignment=TextAnchor.MiddleCenter };
        }

        private static GUIStyle LabelStyle(int size,FontStyle weight,Color color)
        {
            var style=new GUIStyle(GUI.skin.label) { fontSize=size, fontStyle=weight };
            style.normal.textColor=color;
            return style;
        }

        private void Fill(Rect r,Color color)
        {
            Color old=GUI.color;
            GUI.color=color;
            GUI.DrawTexture(r,white);
            GUI.color=old;
        }

        private void Panel(Rect r,Color accent)
        {
            Fill(r,Ink);
            Fill(new Rect(r.x,r.y,r.width,3),accent);
        }

        private void Meter(Rect r,float ratio,Color color)
        {
            Fill(r,Models.Tint("405365"));
            r.width*=Mathf.Clamp01(ratio);
            Fill(r,color);
        }

        private void OnGUI()
        {
            if (view==null) return;
            Skin();
            float scale=Mathf.Min(Screen.width/1080f,Screen.height/720f);
            float w=Screen.width/scale,h=Screen.height/scale;
            GUI.matrix=Matrix4x4.Scale(new Vector3(scale,scale,1));
            if (state==ScreenState.Title)
            {
                Fill(new Rect(0,0,w,h),new Color(.06f,.13f,.19f,.31f));
                DrawTitle(h);
                return;
            }
            DrawHud(w,h);
            if (state==ScreenState.Playing)
            {
                Vector2 at=new(Input.mousePosition.x/scale,(Screen.height-Input.mousePosition.y)/scale);
                Fill(new Rect(at.x-10,at.y,7,2),Pale);
                Fill(new Rect(at.x+5,at.y,7,2),Pale);
                Fill(new Rect(at.x,at.y-10,2,7),Pale);
                Fill(new Rect(at.x,at.y+5,2,7),Pale);
                return;
            }
            Fill(new Rect(0,0,w,h),new Color(.03f,.08f,.14f,.71f));
            if (state==ScreenState.Upgrade) DrawUpgrade(w,h);
            else DrawPause(w,h);
        }

        private void DrawTitle(float h)
        {
            float x=40,y=(h-514)/2;
            Panel(new Rect(x,y,504,514),Gold);
            GUI.Label(new Rect(x+28,y+29,445,82),"ЗОНА 04",headline);
            GUI.Label(new Rect(x+32,y+120,436,28),"ОДИН ПРОТИВ ОРДЫ",text);
            GUI.Label(new Rect(x+32,y+171,436,26),"Сложность",small);
            string[] levels={"Разведка","Выживание","Кошмар"};
            for(int i=0;i<3;i++)
            {
                var r=new Rect(x+32+i*145,y+200,135,41);
                Color old=GUI.color;
                if(difficulty==i) GUI.color=Gold;
                if(GUI.Button(r,levels[i],button))
                {
                    difficulty=i;
                    PlayerPrefs.SetInt("Zone04.Difficulty",i);
                    PlayerPrefs.Save();
                }
                GUI.color=old;
            }
            if(GUI.Button(new Rect(x+32,y+267,440,53),"1   Классическая карта",button)) StartMatch(false);
            if(GUI.Button(new Rect(x+32,y+329,440,53),"2   Случайная карта",button)) StartMatch(true);
            if(GUI.Button(new Rect(x+32,y+400,214,38),"Режим экрана · F11",button))
                SetDisplay(Screen.fullScreenMode==FullScreenMode.Windowed);
            if(GUI.Button(new Rect(x+258,y+400,214,38),"Выйти",button)) Application.Quit();
            GUI.Label(new Rect(x+32,y+464,440,24),"WASD — движение    ЛКМ — огонь    Пробел — рывок",small);
        }

        private void DrawHud(float w,float h)
        {
            Panel(new Rect(22,22,240,78),Mint);
            GUI.Label(new Rect(36,33,208,28),"ЗОНА 04",text);
            GUI.Label(new Rect(36,64,208,25),generated?"Случайная карта":"Классическая карта",small);

            float x=w/2-143;
            Panel(new Rect(x,22,286,78),Gold);
            string waveLabel=remaining+enemies.Count>0 ? $"Волна {wave:00}" : $"До волны {wave+1:00} · {Mathf.CeilToInt(rest)} с";
            GUI.Label(new Rect(x+16,33,252,28),waveLabel,text);
            GUI.Label(new Rect(x+16,64,254,25),$"Врагов {remaining+enemies.Count}  ·  Устранено {kills}",small);
            if(elapsed<noticeUntil)
                GUI.Label(new Rect(x,107,288,27),notice,text);

            Panel(new Rect(22,h-105,244,83),hp<32?Models.Tint("F29288"):Mint);
            GUI.Label(new Rect(36,h-94,210,28),$"Здоровье {Mathf.CeilToInt(hp)} / 100",text);
            Meter(new Rect(36,h-53,214,6),hp/100,Mint);

            Panel(new Rect(x,h-105,286,83),Mint);
            GUI.Label(new Rect(x+16,h-95,254,27),$"Уровень {level} · Опыт {xp}/{XpGoal}",text);
            Meter(new Rect(x+16,h-64,254,4),xp/(float)XpGoal,Mint);
            string dash=elapsed>=dashReady?"Пробел · Рывок готов":$"Рывок через {dashReady-elapsed:0.0} с";
            GUI.Label(new Rect(x+16,h-58,248,23),dash,small);

            x=w-300;
            Panel(new Rect(x,h-105,278,83),Gold);
            GUI.Label(new Rect(x+16,h-96,241,26),Weapons[weaponId].Name,small);
            GUI.Label(new Rect(x+16,h-69,241,31),reloadTimer>0?"Перезарядка":$"{magazine:00} / {ammo:000}   [R]",text);

            if(showMap) DrawMap(w);
            Supply supply=Nearby(false), gun=Nearby(true);
            if(supply!=null || gun!=null)
            {
                string hint=(supply!=null?"E  Подобрать припасы":"")+
                    (gun!=null?(supply!=null?"    ·    ":"")+"F  "+Weapons[gun.Weapon].Name:"");
                var r=new Rect(w/2-230,h-151,460,34);
                Panel(r,Gold);
                GUI.Label(new Rect(r.x+12,r.y+5,r.width-24,25),hint,small);
            }
        }

        private void DrawMap(float w)
        {
            var r=new Rect(w-175,22,153,171);
            Panel(r,Mint);
            GUI.Label(new Rect(r.x+10,r.y+8,133,22),"КАРТА  /  ESC ПАУЗА",small);
            Fill(new Rect(r.x+10,r.y+36,133,125),Models.Tint("34485A"));
            foreach(Enemy enemy in enemies)
            {
                float x=r.x+76+enemy.Position.x*1.42f,y=r.y+98-enemy.Position.y*1.31f;
                Fill(new Rect(x,y,3,3),Models.Tint("F8988B"));
            }
            Fill(new Rect(r.x+74+position.x*1.42f,r.y+96-position.y*1.31f,5,5),Mint);
        }

        private void DrawUpgrade(float w,float h)
        {
            float x=w/2-467,y=h/2-132;
            Panel(new Rect(x,y,934,264),Gold);
            GUI.Label(new Rect(x+27,y+17,880,85),"Уровень "+level,headline);
            for(int i=0;i<3;i++)
            {
                int choice=choices[i];
                float bx=x+27+i*296;
                if(GUI.Button(new Rect(bx,y+123,278,102),(i+1)+"  "+Upgrades[choice]+"\n"+UpgradeDetails[choice],button))
                {
                    Choose(i);
                    break;
                }
            }
        }

        private void DrawPause(float w,float h)
        {
            float x=w/2-245,y=h/2-184;
            Panel(new Rect(x,y,490,368),Gold);
            bool lost=state==ScreenState.Defeat;
            GUI.Label(new Rect(x+24,y+23,444,83),lost?"ТЫ ПОГИБ":"ПАУЗА",headline);
            GUI.Label(new Rect(x+27,y+111,438,35),$"Волна {wave}  ·  Устранено {kills}  ·  Рекорд {best}",small);
            if(GUI.Button(new Rect(x+26,y+157,438,47),lost?"Сыграть снова":"Продолжить",button))
            {
                if(lost) StartMatch(generated);
                else state=ScreenState.Playing;
            }
            if(GUI.Button(new Rect(x+26,y+216,212,42),"Режим экрана",button))
                SetDisplay(Screen.fullScreenMode==FullScreenMode.Windowed);
            if(GUI.Button(new Rect(x+252,y+216,212,42),showMap?"Мини-карта: вкл.":"Мини-карта: выкл.",button))
            {
                showMap=!showMap;
                PlayerPrefs.SetInt("Zone04.Map",showMap?1:0);
                PlayerPrefs.Save();
            }
            GUI.Label(new Rect(x+26,y+274,152,34),"Громкость",small);
            float changed=GUI.HorizontalSlider(new Rect(x+160,y+284,303,24),volume,0,1);
            if(!Mathf.Approximately(volume,changed))
            {
                volume=changed;
                PlayerPrefs.SetFloat("Zone04.Volume",volume);
                PlayerPrefs.Save();
            }
            if(GUI.Button(new Rect(x+26,y+311,438,42),"Главное меню",button))
            {
                StartMatch(generated);
                state=ScreenState.Title;
                FocusCamera(position-Vector2.right*4,true);
            }
        }
    }
}
