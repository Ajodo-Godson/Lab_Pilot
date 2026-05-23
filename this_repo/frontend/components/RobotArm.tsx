"use client";

import { forwardRef, useImperativeHandle, useRef } from "react";
import { Group, Mesh, MeshPhongMaterial } from "three";
import { useFrame } from "@react-three/fiber";

export type RobotArmHandle = {
  updateArm: (tx: number, ty: number, tz: number) => void;
};

type Props = {
  anomaly: boolean;
};

const BASE = { x: 11, y: 13, z: 11 };
const L1 = 8;
const L2 = 6;

function lerp(current: number, target: number, amount: number) {
  return current + (target - current) * amount;
}

const RobotArm = forwardRef<RobotArmHandle, Props>(function RobotArm({ anomaly }, ref) {
  const shoulderRef = useRef<Group>(null);
  const elbowRef = useRef<Group>(null);
  const tipRef = useRef<Mesh>(null);
  const targetRef = useRef({ azimuth: -2.35, shoulder: -0.75, elbow: 1.1 });

  useImperativeHandle(ref, () => ({
    updateArm(tx, ty, tz) {
      const dx = tx - BASE.x;
      const dz = tz - BASE.z;
      const horizontal = Math.max(0.001, Math.hypot(dx, dz));
      const dy = ty - BASE.y;
      const distance = Math.min(L1 + L2 - 0.01, Math.max(0.01, Math.hypot(horizontal, dy)));

      const azimuth = Math.atan2(dx, dz);
      const elbowCos = (L1 * L1 + L2 * L2 - distance * distance) / (2 * L1 * L2);
      const elbow = Math.PI - Math.acos(Math.min(1, Math.max(-1, elbowCos)));
      const shoulderCos = (L1 * L1 + distance * distance - L2 * L2) / (2 * L1 * distance);
      const shoulder = Math.atan2(dy, horizontal) - Math.acos(Math.min(1, Math.max(-1, shoulderCos)));

      targetRef.current = { azimuth, shoulder, elbow };
    },
  }));

  useFrame(({ clock }) => {
    if (shoulderRef.current) {
      shoulderRef.current.rotation.y = lerp(shoulderRef.current.rotation.y, targetRef.current.azimuth, 0.12);
      shoulderRef.current.rotation.z = lerp(shoulderRef.current.rotation.z, targetRef.current.shoulder, 0.12);
    }
    if (elbowRef.current) {
      elbowRef.current.rotation.z = lerp(elbowRef.current.rotation.z, targetRef.current.elbow, 0.12);
    }
    if (tipRef.current) {
      const pulse = anomaly ? 0.65 + Math.sin(clock.elapsedTime * 9) * 0.35 : 0;
      tipRef.current.scale.setScalar(anomaly ? 1 + pulse * 0.35 : 1);
      const material = (Array.isArray(tipRef.current.material) ? tipRef.current.material[0] : tipRef.current.material) as MeshPhongMaterial;
      material.color.set(anomaly ? "#ff1020" : "#ffd84d");
      material.emissive.set(anomaly ? "#ff1020" : "#5f4a00");
    }
  });

  return (
    <group position={[BASE.x, BASE.y, BASE.z]}>
      <mesh>
        <sphereGeometry args={[0.7, 24, 24]} />
        <meshPhongMaterial color="#667788" />
      </mesh>
      <group ref={shoulderRef}>
        <mesh position={[0, L1 / 2, 0]}>
          <cylinderGeometry args={[0.15, 0.15, L1, 18]} />
          <meshPhongMaterial color="#667788" />
        </mesh>
        <mesh position={[0, L1, 0]}>
          <sphereGeometry args={[0.5, 24, 24]} />
          <meshPhongMaterial color="#667788" />
        </mesh>
        <group ref={elbowRef} position={[0, L1, 0]}>
          <mesh position={[0, L2 / 2, 0]}>
            <cylinderGeometry args={[0.12, 0.12, L2, 18]} />
            <meshPhongMaterial color="#667788" />
          </mesh>
          <mesh position={[0, L2, 0]}>
            <sphereGeometry args={[0.35, 24, 24]} />
            <meshPhongMaterial color="#667788" />
          </mesh>
          <mesh position={[0, L2 + 2, 0]}>
            <cylinderGeometry args={[0.08, 0.08, 4, 18]} />
            <meshPhongMaterial color="#667788" />
          </mesh>
          <mesh ref={tipRef} position={[0, L2 + 4.1, 0]}>
            <sphereGeometry args={[0.38, 24, 24]} />
            <meshPhongMaterial color="#ffd84d" emissive="#5f4a00" emissiveIntensity={1.4} />
          </mesh>
        </group>
      </group>
    </group>
  );
});

export default RobotArm;
