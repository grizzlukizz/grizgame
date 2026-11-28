Shader "Zone04/Surface"
{
    Properties
    {
        _Color ("Color", Color) = (1,1,1,1)
        _Glossiness ("Smoothness", Range(0,1)) = 0.22
        _Metallic ("Metallic", Range(0,1)) = 0
    }
    SubShader
    {
        Tags { "RenderType"="Opaque" }
        LOD 200
        CGPROGRAM
        #pragma surface surf Standard fullforwardshadows addshadow
        #pragma target 3.0

        struct Input { float3 worldPos; };
        fixed4 _Color;
        half _Glossiness;
        half _Metallic;

        void surf(Input info, inout SurfaceOutputStandard o)
        {
            o.Albedo = _Color.rgb;
            o.Smoothness = _Glossiness;
            o.Metallic = _Metallic;
            o.Alpha = 1;
        }
        ENDCG
    }
    Fallback "Diffuse"
}
