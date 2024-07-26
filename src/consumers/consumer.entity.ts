import { ConsumerEnum } from '@/common/enums/consumers.enum';
import { PaletteVariants } from '@/common/enums/palette-variants.enum';
import { Provider } from '@/providers/provider.entity';
import { Entity, PrimaryGeneratedColumn, Column, ManyToOne } from 'typeorm';

@Entity()
export class Consumer {
  @PrimaryGeneratedColumn('uuid')
  id: string;

  @Column()
  name: string;

  @Column({
    type: 'text',
    enum: ConsumerEnum,
  })
  type: ConsumerEnum;

  @Column()
  identifier: string;

  @Column({
    type: 'text',
    enum: PaletteVariants,
    default: PaletteVariants.Vibrant,
  })
  pallete: PaletteVariants;

  @ManyToOne(() => Provider, (provider) => provider.consumers)
  provider: Provider;
}
