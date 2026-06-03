'use client';

import React from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { IoTicketOutline } from 'react-icons/io5';
import { useCreateTicket } from '@/services/api/tickets';
import { useSendReply } from '@/services/api/chats';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription } from '@/components/ui/dialog';
import { Field, FieldLabel, FieldError } from '@/components/ui/field';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { toast } from 'sonner';

const ticketSchema = z.object({
  title: z.string().min(1, 'Title is required.'),
  description: z.string().min(1, 'Description is required.'),
  priority: z.enum(['low', 'medium', 'high', 'urgent']),
  customer_name: z.string().optional(),
  customer_phone: z.string().optional(),
});

type TicketFormData = z.infer<typeof ticketSchema>;

interface CreateTicketModalProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  selectedChat: { platform: string; senderId: string } | null;
  customerName?: string;
}

export const CreateTicketModal = ({ open, onOpenChange, selectedChat, customerName }: CreateTicketModalProps) => {
  const createTicketMutation = useCreateTicket();
  const sendReplyMutation = useSendReply();

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<TicketFormData>({
    resolver: zodResolver(ticketSchema),
    defaultValues: {
      title: '',
      description: '',
      priority: 'medium',
      customer_name: customerName || '',
      customer_phone: '',
    },
  });

  React.useEffect(() => {
    if (open) {
      reset({
        title: '',
        description: '',
        priority: 'medium',
        customer_name: customerName || '',
        customer_phone: '',
      });
    }
  }, [open, customerName, reset]);

  const onSubmit = async (data: TicketFormData) => {
    if (!selectedChat) return;
    try {
      const res = await createTicketMutation.mutateAsync({
        title: data.title,
        description: data.description,
        priority: data.priority,
        customer_name: data.customer_name || undefined,
        customer_phone: data.customer_phone || undefined,
      });

      if (res.tracking_token) {
        const trackingUrl = `${window.location.origin}/track-your-ticket/${res.tracking_token}`;
        const trackingMessage = `Your support ticket "${data.title}" has been registered. Track it here: \n ${trackingUrl}`;
        await sendReplyMutation.mutateAsync({
          sender_id: selectedChat.senderId,
          platform: selectedChat.platform,
          text: trackingMessage
        });
      }

      toast.success('Ticket created and tracking link sent!');
      
      onOpenChange(false);
      reset();
    } catch (error) {
      const errMessage = error instanceof Error ? error.message : 'Failed to create ticket.';
      toast.error(errMessage);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-[480px] bg-white border border-slate-100 rounded-2xl shadow-2xl p-6">
        <DialogHeader className="space-y-2">
          <div className="w-12 h-12 rounded-xl bg-indigo-50 border border-indigo-100/50 flex items-center justify-center text-indigo-600 mb-2">
            <IoTicketOutline className="w-6 h-6" />
          </div>
          <DialogTitle className="text-xl font-bold text-slate-900">Create Support Ticket</DialogTitle>
          <DialogDescription className="text-sm text-slate-500">
            Create a support ticket for the customer. They can track the status using a secure link.
          </DialogDescription>
        </DialogHeader>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4 mt-4">
          <Field>
            <FieldLabel htmlFor="title" className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
              Ticket Title
            </FieldLabel>
            <Input
              id="title"
              placeholder="e.g., Delivery delayed, Incorrect item received"
              {...register('title')}
              className="mt-1 h-10 border-slate-200 focus:border-indigo-500 focus:ring-indigo-500 bg-white"
            />
            <FieldError errors={[errors.title]} />
          </Field>

          <Field>
            <FieldLabel htmlFor="description" className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
              Description
            </FieldLabel>
            <textarea
              id="description"
              placeholder="Describe the customer's query or problem..."
              {...register('description')}
              rows={3}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-sm transition-colors outline-none focus-visible:border-indigo-500 focus-visible:ring-3 focus-visible:ring-indigo-500/10 min-h-[80px]"
            />
            <FieldError errors={[errors.description]} />
          </Field>

          <div className="grid grid-cols-2 gap-4">
            <Field>
              <FieldLabel htmlFor="priority" className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Priority
              </FieldLabel>
              <select
                id="priority"
                {...register('priority')}
                className="mt-1 w-full h-10 rounded-lg border border-slate-200 bg-white px-2.5 text-sm transition-colors outline-none focus-visible:border-indigo-500 focus-visible:ring-3 focus-visible:ring-indigo-500/10"
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
                <option value="urgent">Urgent</option>
              </select>
              <FieldError errors={[errors.priority]} />
            </Field>

            <Field>
              <FieldLabel htmlFor="customer_phone" className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
                Customer Phone
              </FieldLabel>
              <Input
                id="customer_phone"
                placeholder="Phone number"
                {...register('customer_phone')}
                className="mt-1 h-10 border-slate-200 focus:border-indigo-500 focus:ring-indigo-500 bg-white"
              />
              <FieldError errors={[errors.customer_phone]} />
            </Field>
          </div>

          <Field>
            <FieldLabel htmlFor="customer_name" className="text-xs font-semibold text-slate-600 uppercase tracking-wider">
              Customer Name
            </FieldLabel>
            <Input
              id="customer_name"
              placeholder="Name"
              {...register('customer_name')}
              className="mt-1 h-10 border-slate-200 focus:border-indigo-500 focus:ring-indigo-500 bg-white"
            />
            <FieldError errors={[errors.customer_name]} />
          </Field>

          <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-100 mt-6">
            <Button
              type="button"
              variant="outline"
              onClick={() => onOpenChange(false)}
              className="h-10 px-4 rounded-xl font-semibold border-slate-200 text-slate-600 hover:bg-slate-50 cursor-pointer"
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={isSubmitting}
              className="h-10 px-4 rounded-xl font-semibold bg-indigo-600 text-white hover:bg-indigo-700 active:scale-95 transition-all shadow-md shadow-indigo-100 cursor-pointer"
            >
              {isSubmitting ? 'Creating...' : 'Create Ticket'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
};
