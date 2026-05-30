import { OrderDetail } from '@/components/orders/OrderDetail';

interface PageProps {
  params: Promise<{ id: string }>;
}

export default async function OrderPage({ params }: PageProps) {
  const { id } = await params;
  return <OrderDetail id={id} />;
}
