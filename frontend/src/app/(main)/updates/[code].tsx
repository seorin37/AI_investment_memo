import React from 'react';
import { useLocalSearchParams } from 'expo-router';
import { StockUpdatesList } from '@/features/updates/UpdatesScreens';

export default function StockUpdatesScreen() {
  const { code } = useLocalSearchParams<{ code: string }>();
  return <StockUpdatesList code={code} />;
}
