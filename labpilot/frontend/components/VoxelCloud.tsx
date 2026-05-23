"use client";

import { forwardRef, useEffect, useImperativeHandle, useMemo, useRef } from "react";
import { Color, InstancedMesh, InstancedBufferAttribute, Matrix4, Object3D } from "three";
import { useFrame } from "@react-three/fiber";

export type SARPoint = {
  x: number;
  y: number;
  z: number;
  frequency_mhz: number;
  power_dbm: number;
  sar_w_kg: number;
  is_anomaly: boolean;
  pct_of_limit: number;
};

export type VoxelCloudHandle = {
  addPoint: (point: SARPoint) => void;
  reset: () => void;
};

type Props = {
  onPointAdded?: (point: SARPoint) => void;
};

const MAX_POINTS = 10000;

function colorForPct(pct: number) {
  if (pct < 0.18) return "#1044bb";
  if (pct < 0.38) return "#1a9980";
  if (pct < 0.62) return "#f09510";
  if (pct < 0.85) return "#e03010";
  return "#ff1020";
}

const VoxelCloud = forwardRef<VoxelCloudHandle, Props>(function VoxelCloud({ onPointAdded }, ref) {
  const meshRef = useRef<InstancedMesh>(null);
  const cursorRef = useRef(0);
  const pointsRef = useRef<Array<SARPoint | null>>(Array.from({ length: MAX_POINTS }, () => null));
  const dummy = useMemo(() => new Object3D(), []);
  const hiddenMatrix = useMemo(() => new Matrix4().makeScale(0.001, 0.001, 0.001), []);
  const color = useMemo(() => new Color(), []);

  function hideAll() {
    const mesh = meshRef.current;
    if (!mesh) return;
    for (let i = 0; i < MAX_POINTS; i += 1) {
      mesh.setMatrixAt(i, hiddenMatrix);
      mesh.setColorAt(i, color.set("#000000"));
      pointsRef.current[i] = null;
    }
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  }

  useEffect(() => {
    const mesh = meshRef.current;
    if (mesh) {
      const colors = new Float32Array(MAX_POINTS * 3);
      mesh.instanceColor = new InstancedBufferAttribute(colors, 3);
      hideAll();
    }
  }, []);

  useImperativeHandle(ref, () => ({
    addPoint(point) {
      const mesh = meshRef.current;
      if (!mesh) return;
      const index = cursorRef.current % MAX_POINTS;
      dummy.position.set(point.x, point.y, point.z);
      dummy.scale.setScalar(1);
      dummy.updateMatrix();
      mesh.setMatrixAt(index, dummy.matrix);
      mesh.setColorAt(index, color.set(colorForPct(point.pct_of_limit)));
      mesh.instanceMatrix.needsUpdate = true;
      if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
      pointsRef.current[index] = point;
      cursorRef.current += 1;
      onPointAdded?.(point);
    },
    reset() {
      cursorRef.current = 0;
      hideAll();
    },
  }));

  useFrame(({ clock }) => {
    const mesh = meshRef.current;
    if (!mesh) return;
    const scale = 0.99 + Math.sin(clock.elapsedTime * 9) * 0.21;
    let changed = false;
    pointsRef.current.forEach((point, index) => {
      if (!point?.is_anomaly) return;
      dummy.position.set(point.x, point.y, point.z);
      dummy.scale.setScalar(scale);
      dummy.updateMatrix();
      mesh.setMatrixAt(index, dummy.matrix);
      changed = true;
    });
    if (changed) mesh.instanceMatrix.needsUpdate = true;
  });

  return (
    <instancedMesh ref={meshRef} args={[undefined, undefined, MAX_POINTS]}>
      <boxGeometry args={[0.62, 0.62, 0.62]} />
      <meshBasicMaterial vertexColors transparent opacity={0.92} />
    </instancedMesh>
  );
});

export default VoxelCloud;
